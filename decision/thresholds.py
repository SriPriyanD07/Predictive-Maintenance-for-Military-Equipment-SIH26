"""
decision/thresholds.py

Centralized, tunable configuration for the predictive-maintenance decision
engine. This module contains CONSTANTS AND LOOKUP TABLES ONLY — no decision
logic, no calculations, no control flow beyond simple literal data.

Owned by: Member 2 (Decision Intelligence)
Consumed by: decision/engine.py (not implemented here)

Frozen contract this config supports (defined/enforced in engine.py):

    def decide(rul, window, history):
        ...
        return {
            "health_index": ...,
            "risk_score": ...,
            "risk_level": ...,        # one of RISK_LEVELS
            "priority": ...,          # one of RISK_LEVEL_TO_PRIORITY.values()
            "action_code": ...,       # one of ACTION_CODES
            "recommended_action": ...,# RECOMMENDED_ACTIONS[action_code]
            "reason": ...,
        }

Do not add classes, frameworks, I/O, network calls, or global mutable
runtime state here. Everything below is plain, immutable, standard-library
data.
"""

# ---------------------------------------------------------------------------
# 1. Core normalization constant
# ---------------------------------------------------------------------------

# Used by engine.py as: health_index = clamp(rul / MAX_RUL, 0, 1)
#                        rul_risk     = 1 - clamp(rul / MAX_RUL, 0, 1)
MAX_RUL = 125.0


# ---------------------------------------------------------------------------
# 2. RUL band boundaries (single source of truth — tune here only)
# ---------------------------------------------------------------------------

# Each *_MIN constant is the inclusive lower bound (in RUL units) of the
# named band. Bands are half-open: [this_min, next_min_up).
RUL_NOMINAL_MIN = 80.0            # rul >= 80              -> NOMINAL
RUL_WATCH_MIN = 50.0              # 50 <= rul < 80          -> WATCH
RUL_WARNING_MIN = 25.0            # 25 <= rul < 50          -> WARNING
RUL_CRITICAL_SERVICE_MIN = 10.0   # 10 <= rul < 25          -> CRITICAL / SERVICE_24H
# rul < RUL_CRITICAL_SERVICE_MIN                            -> CRITICAL / GROUND_NOW


# ---------------------------------------------------------------------------
# 3. Risk-level ordering (severity, low -> high)
# ---------------------------------------------------------------------------

# engine.py can compare severity via RISK_LEVELS.index(level_a) < .index(level_b)
RISK_LEVELS = ("NOMINAL", "WATCH", "WARNING", "CRITICAL")


# ---------------------------------------------------------------------------
# 4. Priority mapping
# ---------------------------------------------------------------------------

RISK_LEVEL_TO_PRIORITY = {
    "NOMINAL": "P4",
    "WATCH": "P3",
    "WARNING": "P2",
    "CRITICAL": "P1",
}


# ---------------------------------------------------------------------------
# 5. RUL bands -> (risk_level, action_code) — the action-code mapping
# ---------------------------------------------------------------------------

# Ordered ascending by floor. Lowest floor is -inf so every possible rul
# value (including 0 or a noisy negative reading) resolves to exactly one
# band with no gaps and no overlap.
#
# engine.py usage pattern:
#   band = next(b for b in reversed(RUL_BANDS) if rul >= b[0])
#   risk_level, action_code = band[1], band[2]
ACTION_CODES = ("MONITOR", "INSPECT_7D", "SCHEDULE_72H", "SERVICE_24H", "GROUND_NOW")

RUL_BANDS = (
    (float("-inf"), "CRITICAL", "GROUND_NOW"),
    (RUL_CRITICAL_SERVICE_MIN, "CRITICAL", "SERVICE_24H"),
    (RUL_WARNING_MIN, "WARNING", "SCHEDULE_72H"),
    (RUL_WATCH_MIN, "WATCH", "INSPECT_7D"),
    (RUL_NOMINAL_MIN, "NOMINAL", "MONITOR"),
)


# ---------------------------------------------------------------------------
# 6. Recommended-action text, keyed by action_code
# ---------------------------------------------------------------------------

RECOMMENDED_ACTIONS = {
    "MONITOR": "Continue normal operation",
    "INSPECT_7D": "Inspect at next 7-day window",
    "SCHEDULE_72H": "Schedule maintenance within 72 h",
    "SERVICE_24H": "Ground unit — service within 24 h",
    "GROUND_NOW": "Immediate grounding — do not dispatch",
}


# ---------------------------------------------------------------------------
# 7. Risk weights (must sum to 1.0)
# ---------------------------------------------------------------------------

RISK_WEIGHTS = {
    "rul": 0.60,
    "trend": 0.25,
    "anomaly": 0.15,
}


# ---------------------------------------------------------------------------
# 8. Hysteresis margins (RUL units), keyed by the boundary they guard
# ---------------------------------------------------------------------------

# engine.py (which owns transition state) can use these to require rul to
# clear a boundary by the given margin before flipping risk_level back the
# other way, preventing WATCH<->WARNING and WARNING<->CRITICAL flapping.
# Larger margins sit on the boundaries most likely to be hovered near.

RISK_SCORE_ESCALATION_THRESHOLD = 0.75
HYSTERESIS_MARGINS = {
    RUL_NOMINAL_MIN: 5.0,
    RUL_WATCH_MIN: 5.0,
    RUL_WARNING_MIN: 5.0,
    RUL_CRITICAL_SERVICE_MIN: 2.0,
}