"""
decision/engine.py

Decision Intelligence engine for the predictive-maintenance backend.

Frozen public contract:

    def decide(rul, window, history):
        return {
            "health_index": float,
            "risk_score": float,
            "risk_level": str,
            "priority": str,
            "action_code": str,
            "recommended_action": str,
            "reason": str,
        }

Decision architecture:
    1. RUL is the primary failure-proximity signal.
    2. RUL trend measures degradation velocity.
    3. Telemetry anomaly measures abnormal current behaviour.
    4. The three signals are fused using configured weights.
    5. RUL bands provide the primary operational classification.
    6. High fused risk may escalate the classification by one band.
    7. Hysteresis prevents rapid downgrade/flicker.

No I/O, networking, database, or external dependencies.
"""

import math

from decision import thresholds


# ---------------------------------------------------------------------------
# Internal constants
# ---------------------------------------------------------------------------

_TELEMETRY_KEYS = (
    "core_temp",
    "exhaust_temp",
    "pressure",
    "fuel_flow",
    "vibration",
    "fan_speed",
    "core_speed",
)

_ANOMALY_Z_CAP = 3.0
_TREND_WINDOW = 20


# ---------------------------------------------------------------------------
# Numeric helpers
# ---------------------------------------------------------------------------

def _clamp(value, lo, hi):
    """Clamp value into the inclusive range [lo, hi]."""
    return max(lo, min(hi, value))


def _safe_float(value):
    """Convert value to finite float, otherwise return None."""
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(result):
        return None

    return result


# ---------------------------------------------------------------------------
# Trend risk
# ---------------------------------------------------------------------------

def _extract_recent_rul_values(history, limit=_TREND_WINDOW):
    """Extract recent valid RUL values from history."""
    values = []

    try:
        entries = list(history)
    except (TypeError, ValueError):
        return values

    for entry in entries[-limit:]:
        if not hasattr(entry, "get"):
            continue

        value = _safe_float(entry.get("rul"))

        if value is not None:
            values.append(value)

    return values


def _compute_trend_risk(history):
    """
    Calculate degradation trend.

    Returns:
        (trend_risk, slope)

    slope:
        RUL cycles per history point.

    Only a negative slope contributes risk.
    """
    try:
        values = _extract_recent_rul_values(history)

        n = len(values)

        if n < 2:
            return 0.0, 0.0

        xs = list(range(n))

        x_mean = sum(xs) / n
        y_mean = sum(values) / n

        numerator = sum(
            (x - x_mean) * (y - y_mean)
            for x, y in zip(xs, values)
        )

        denominator = sum(
            (x - x_mean) ** 2
            for x in xs
        )

        if denominator == 0:
            return 0.0, 0.0

        slope = numerator / denominator

        if not math.isfinite(slope):
            return 0.0, 0.0

        # Only decreasing RUL represents deterioration.
        decline = max(0.0, -slope)

        # A decline capable of consuming MAX_RUL during this window
        # represents severe degradation.
        severe_slope = thresholds.MAX_RUL / n

        if severe_slope <= 0:
            return 0.0, slope

        trend_risk = _clamp(
            decline / severe_slope,
            0.0,
            1.0,
        )

        return trend_risk, slope

    except Exception:
        return 0.0, 0.0


# ---------------------------------------------------------------------------
# Telemetry anomaly risk
# ---------------------------------------------------------------------------

def _compute_anomaly_risk(window):
    """
    Compare the latest telemetry observation against previous observations.

    Returns:
        (anomaly_risk, dominant_channel, z_score)

    The latest observation is deliberately excluded from its own baseline.
    """
    try:
        samples = list(window)
    except (TypeError, ValueError):
        return 0.0, None, 0.0

    if len(samples) < 3:
        return 0.0, None, 0.0

    worst_channel = None
    worst_z = 0.0

    # Previous samples = baseline.
    # Latest sample = observation being tested.
    baseline_samples = samples[:-1]
    latest_sample = samples[-1]

    for key in _TELEMETRY_KEYS:

        baseline_values = []

        for entry in baseline_samples:
            if not hasattr(entry, "get"):
                continue

            value = _safe_float(entry.get(key))

            if value is not None:
                baseline_values.append(value)

        if not hasattr(latest_sample, "get"):
            continue

        latest_value = _safe_float(
            latest_sample.get(key)
        )

        if latest_value is None:
            continue

        if len(baseline_values) < 2:
            continue

        mean = sum(baseline_values) / len(baseline_values)

        variance = sum(
            (value - mean) ** 2
            for value in baseline_values
        ) / len(baseline_values)

        if variance <= 0:
            continue

        std_dev = math.sqrt(variance)

        if std_dev <= 0:
            continue

        z_score = (latest_value - mean) / std_dev

        if not math.isfinite(z_score):
            continue

        if abs(z_score) > abs(worst_z):
            worst_z = z_score
            worst_channel = key

    anomaly_risk = _clamp(
        abs(worst_z) / _ANOMALY_Z_CAP,
        0.0,
        1.0,
    )

    return anomaly_risk, worst_channel, worst_z


# ---------------------------------------------------------------------------
# RUL band helpers
# ---------------------------------------------------------------------------

def _band_index_for_rul(rul_value):
    """
    Return the RUL_BANDS index for a given RUL.

    RUL_BANDS is ordered from most severe to least severe:

        0 = GROUND_NOW
        1 = SERVICE_24H
        2 = SCHEDULE_72H
        3 = INSPECT_7D
        4 = MONITOR
    """
    index = 0

    for i, band in enumerate(thresholds.RUL_BANDS):

        if rul_value >= band[0]:
            index = i
        else:
            break

    return index


def _band_index_for_action_code(action_code):
    """Return the band index associated with an action code."""
    for i, band in enumerate(thresholds.RUL_BANDS):
        if band[2] == action_code:
            return i

    return None


def _band_index_for_level(risk_level):
    """
    Return the least severe band belonging to a risk level.

    Used when historical data contains risk_level but no action_code.
    """
    matches = [
        i
        for i, band in enumerate(thresholds.RUL_BANDS)
        if band[1] == risk_level
    ]

    return max(matches) if matches else None


# ---------------------------------------------------------------------------
# Historical state
# ---------------------------------------------------------------------------

def _extract_previous_state(history):
    """
    Find the latest valid risk level and action code.

    Returns:
        (risk_level, action_code)
    """
    try:
        entries = list(history)
    except (TypeError, ValueError):
        return None, None

    for entry in reversed(entries):

        if not hasattr(entry, "get"):
            continue

        risk_level = entry.get("risk_level")

        if risk_level not in thresholds.RISK_LEVELS:
            continue

        action_code = entry.get("action_code")

        if action_code not in thresholds.ACTION_CODES:
            action_code = None

        return risk_level, action_code

    return None, None


# ---------------------------------------------------------------------------
# Risk fusion escalation
# ---------------------------------------------------------------------------

def _apply_risk_escalation(rul_value, risk_score):
    """
    Start with the RUL-based operational band.

    If the fused risk score reaches the configured escalation threshold,
    move exactly ONE band toward greater severity.

    Risk fusion can escalate, but never downgrade the RUL policy.
    """
    natural_index = _band_index_for_rul(rul_value)

    threshold = getattr(
        thresholds,
        "RISK_SCORE_ESCALATION_THRESHOLD",
        0.75,
    )

    threshold = _safe_float(threshold)

    if threshold is None:
        threshold = 0.75

    # No escalation required.
    if risk_score < threshold:
        return natural_index

    # Already at maximum severity.
    if natural_index <= 0:
        return natural_index

    # Conservative one-level escalation.
    return natural_index - 1


# ---------------------------------------------------------------------------
# Hysteresis
# ---------------------------------------------------------------------------

def _apply_hysteresis(rul_value, proposed_index, history):
    """
    Prevent rapid downgrading around RUL boundaries.

    Escalation:
        immediate.

    Improvement:
        requires RUL to clear the next boundary plus its hysteresis margin.
    """
    previous_level, previous_action = _extract_previous_state(history)

    if previous_level is None:
        return proposed_index

    if previous_action is not None:
        previous_index = _band_index_for_action_code(
            previous_action
        )
    else:
        previous_index = _band_index_for_level(
            previous_level
        )

    if previous_index is None:
        return proposed_index

    # Smaller index = more severe.
    #
    # proposed_index <= previous_index means:
    # same severity OR escalation.
    if proposed_index <= previous_index:
        return proposed_index

    # Proposed result is less severe.
    # Allow only one-step improvement at a time.
    next_index = previous_index + 1

    if next_index >= len(thresholds.RUL_BANDS):
        return proposed_index

    boundary = thresholds.RUL_BANDS[next_index][0]

    margin = thresholds.HYSTERESIS_MARGINS.get(
        boundary,
        0.0,
    )

    margin = _safe_float(margin)

    if margin is None:
        margin = 0.0

    # Require meaningful improvement beyond the boundary.
    if rul_value >= boundary + margin:
        return proposed_index

    # Not enough improvement: hold previous severity.
    return previous_index


# ---------------------------------------------------------------------------
# Reason generation
# ---------------------------------------------------------------------------

def _build_reason(
    rul_value,
    rul_risk,
    trend_risk,
    trend_slope,
    anomaly_risk,
    anomaly_key,
    anomaly_z,
    effective_level,
    effective_action,
    natural_index,
    effective_index,
):
    """
    Generate a short explainability statement.

    The dominant weighted contributor determines the reason.
    """
    try:
        weights = thresholds.RISK_WEIGHTS

        contributions = {
            "rul": (
                weights.get("rul", 0.0) * rul_risk
            ),
            "trend": (
                weights.get("trend", 0.0) * trend_risk
            ),
            "anomaly": (
                weights.get("anomaly", 0.0) * anomaly_risk
            ),
        }

        dominant = max(
            contributions,
            key=contributions.get,
        )

        # If fused risk escalated the natural RUL classification,
        # explicitly mention that supporting evidence caused escalation.
        escalated = effective_index < natural_index

        if dominant == "anomaly" and anomaly_key is not None:
            label = anomaly_key.replace("_", " ")

            text = (
                "Telemetry anomaly: {} {:.1f}σ; RUL {:.1f}."
                .format(
                    label,
                    abs(anomaly_z),
                    rul_value,
                )
            )

        elif dominant == "trend" and trend_slope < 0:
            text = (
                "RUL declining {:.2f} cycles/tick; current RUL {:.1f}."
                .format(
                    abs(trend_slope),
                    rul_value,
                )
            )

        else:
            text = (
                "RUL {:.1f} cycles; classified {}."
                .format(
                    rul_value,
                    effective_level,
                )
            )

        if escalated:
            text += " Fused risk elevated."

        if len(text) > 120:
            text = text[:117].rstrip() + "..."

        return text

    except Exception:
        return (
            "Decision computed from available data."
        )


# ---------------------------------------------------------------------------
# Safe fallback
# ---------------------------------------------------------------------------

def _safe_fallback():
    """
    Guaranteed valid decision when unexpected input/errors occur.
    """
    return {
        "health_index": 1.0,
        "risk_score": 0.0,
        "risk_level": "NOMINAL",
        "priority": "P4",
        "action_code": "MONITOR",
        "recommended_action": "Continue normal operation",
        "reason": "Decision engine fallback; insufficient valid data",
    }


# ---------------------------------------------------------------------------
# Public frozen contract
# ---------------------------------------------------------------------------

def decide(rul, window, history):
    """
    Convert RUL, degradation trend, and telemetry anomalies into
    an actionable maintenance decision.

    This function NEVER raises.
    """
    try:
        # ---------------------------------------------------------------
        # 1. Validate RUL
        # ---------------------------------------------------------------

        rul_value = _safe_float(rul)

        if rul_value is None:
            return _safe_fallback()

        # RUL used for policy classification should remain within
        # the model's expected operating range.
        policy_rul = _clamp(
            rul_value,
            0.0,
            thresholds.MAX_RUL,
        )

        # ---------------------------------------------------------------
        # 2. Primary RUL signal
        # ---------------------------------------------------------------

        rul_fraction = _clamp(
            policy_rul / thresholds.MAX_RUL,
            0.0,
            1.0,
        )

        health_index = rul_fraction
        rul_risk = 1.0 - rul_fraction

        # ---------------------------------------------------------------
        # 3. Trend signal
        # ---------------------------------------------------------------

        trend_risk, trend_slope = _compute_trend_risk(
            history
        )

        # ---------------------------------------------------------------
        # 4. Telemetry anomaly signal
        # ---------------------------------------------------------------

        (
            anomaly_risk,
            anomaly_key,
            anomaly_z,
        ) = _compute_anomaly_risk(window)

        # ---------------------------------------------------------------
        # 5. Weighted risk fusion
        # ---------------------------------------------------------------

        weights = thresholds.RISK_WEIGHTS

        risk_score = (
            weights.get("rul", 0.0) * rul_risk
            + weights.get("trend", 0.0) * trend_risk
            + weights.get("anomaly", 0.0) * anomaly_risk
        )

        risk_score = _clamp(
            risk_score,
            0.0,
            1.0,
        )

        # ---------------------------------------------------------------
        # 6. RUL-based operational policy
        # ---------------------------------------------------------------

        natural_index = _band_index_for_rul(
            policy_rul
        )

        # ---------------------------------------------------------------
        # 7. Allow fused evidence to escalate one band
        # ---------------------------------------------------------------

        proposed_index = _apply_risk_escalation(
            policy_rul,
            risk_score,
        )

        # ---------------------------------------------------------------
        # 8. Apply hysteresis
        # ---------------------------------------------------------------

        effective_index = _apply_hysteresis(
            policy_rul,
            proposed_index,
            history,
        )

        effective_band = thresholds.RUL_BANDS[
            effective_index
        ]

        effective_level = effective_band[1]
        effective_action = effective_band[2]

        # ---------------------------------------------------------------
        # 9. Priority + recommended action
        # ---------------------------------------------------------------

        priority = thresholds.RISK_LEVEL_TO_PRIORITY.get(
            effective_level,
            "P4",
        )

        recommended_action = thresholds.RECOMMENDED_ACTIONS.get(
            effective_action,
            "Continue normal operation",
        )

        # ---------------------------------------------------------------
        # 10. Explainability
        # ---------------------------------------------------------------

        reason = _build_reason(
            rul_value=policy_rul,
            rul_risk=rul_risk,
            trend_risk=trend_risk,
            trend_slope=trend_slope,
            anomaly_risk=anomaly_risk,
            anomaly_key=anomaly_key,
            anomaly_z=anomaly_z,
            effective_level=effective_level,
            effective_action=effective_action,
            natural_index=natural_index,
            effective_index=effective_index,
        )

        # ---------------------------------------------------------------
        # 11. Final contract
        # ---------------------------------------------------------------

        return {
            "health_index": round(
                health_index,
                4,
            ),
            "risk_score": round(
                risk_score,
                4,
            ),
            "risk_level": effective_level,
            "priority": priority,
            "action_code": effective_action,
            "recommended_action": recommended_action,
            "reason": reason,
        }

    except Exception:
        return _safe_fallback()