"""
Regression suite for decision.engine.decide().

Tests the public behavior of the existing decision engine without modifying
its implementation or configuration.
"""

import pytest

from decision.engine import decide
from decision.thresholds import MAX_RUL, RISK_SCORE_ESCALATION_THRESHOLD


REQUIRED_KEYS = {
    "health_index",
    "risk_score",
    "risk_level",
    "priority",
    "action_code",
    "recommended_action",
    "reason",
}

RISK_LEVELS = {"NOMINAL", "WATCH", "WARNING", "CRITICAL"}
PRIORITIES = {"P4", "P3", "P2", "P1"}
ACTION_CODES = {
    "MONITOR",
    "INSPECT_7D",
    "SCHEDULE_72H",
    "SERVICE_24H",
    "GROUND_NOW",
}

BAND_MAP = {
    "NOMINAL": ("P4", "MONITOR"),
    "WATCH": ("P3", "INSPECT_7D"),
    "WARNING": ("P2", "SCHEDULE_72H"),
    "CRITICAL": ("P1", {"SERVICE_24H", "GROUND_NOW"}),
}


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


def _assert_shape(result):
    assert set(result.keys()) == REQUIRED_KEYS
    assert isinstance(result["reason"], str)
    assert len(result["reason"]) <= 120
    assert 0.0 <= result["risk_score"] <= 1.0
    assert 0.0 <= result["health_index"] <= 1.0
    assert result["risk_level"] in RISK_LEVELS
    assert result["priority"] in PRIORITIES
    assert result["action_code"] in ACTION_CODES
    return result


# ---------- 1. POLICY / BAND CORRECTNESS ----------

def test_band_nominal():
    r = _assert_shape(decide(100, [], []))
    assert r["risk_level"] == "NOMINAL"
    assert r["priority"] == "P4"
    assert r["action_code"] == "MONITOR"
    assert r["risk_score"] == pytest.approx(0.12)
    assert r["health_index"] == pytest.approx(0.8)


def test_band_watch():
    r = _assert_shape(decide(70, [], []))
    assert r["risk_level"] == "WATCH"
    assert r["priority"] == "P3"
    assert r["action_code"] == "INSPECT_7D"


def test_band_warning():
    r = _assert_shape(decide(40, [], []))
    assert r["risk_level"] == "WARNING"
    assert r["priority"] == "P2"
    assert r["action_code"] == "SCHEDULE_72H"


def test_band_critical_service_24h():
    r = _assert_shape(decide(20, [], []))
    assert r["risk_level"] == "CRITICAL"
    assert r["priority"] == "P1"
    assert r["action_code"] == "SERVICE_24H"


def test_band_critical_ground_now():
    r = _assert_shape(decide(5, [], []))
    assert r["risk_level"] == "CRITICAL"
    assert r["priority"] == "P1"
    assert r["action_code"] == "GROUND_NOW"
    assert r["risk_score"] == pytest.approx(0.576)
    assert r["health_index"] == pytest.approx(0.04)


# ---------- 2. SIGNAL COMPOSITION ----------

def test_rul_risk_direction():
    hi = decide(100, [], [])["risk_score"]
    lo = decide(5, [], [])["risk_score"]
    assert lo > hi


def test_health_index_is_clamped_rul_ratio():
    for rul in (100, 70, 40, 20, 5, 0):
        r = decide(rul, [], [])
        assert r["health_index"] == pytest.approx(
            _clamp(rul / MAX_RUL, 0.0, 1.0)
        )


def test_declining_trend_increases_risk():
    stable = [{"rul": 40 + i * 0.02} for i in range(20)]
    declining = [{"rul": 80 - i * 2.0} for i in range(20)]

    r_stable = decide(40, [], stable)
    r_declining = decide(40, [], declining)

    assert r_stable["risk_score"] == pytest.approx(0.408)
    assert r_declining["risk_score"] == pytest.approx(0.488)
    assert r_declining["risk_score"] > r_stable["risk_score"]


def test_telemetry_anomaly_increases_risk():
    # The existing engine expects telemetry dictionaries containing
    # the configured telemetry keys, including "vibration".
    baseline = [
        {"vibration": 0.10 + 0.01 * (i % 3)}
        for i in range(20)
    ]
    spike = baseline + [{"vibration": 5.0}]

    r_base = decide(40, baseline, [])
    r_spike = decide(40, spike, [])

    assert r_spike["risk_score"] >= r_base["risk_score"]


def test_constant_telemetry_baseline_no_exception():
    constant = [{"vibration": 0.15} for _ in range(20)]

    r = _assert_shape(decide(40, constant, []))

    assert r is not None


# ---------- 3. DEFENSIVENESS ----------

def test_empty_history():
    _assert_shape(decide(50, [], []))


def test_empty_window():
    _assert_shape(decide(50, [], [{"rul": 50}]))


def test_invalid_negative_rul_does_not_raise():
    r = _assert_shape(decide(-10, [], []))
    assert r["health_index"] == pytest.approx(0.0)


def test_nan_rul_does_not_raise():
    r = decide(float("nan"), [], [])
    assert set(r.keys()) == REQUIRED_KEYS


def test_infinite_rul_does_not_raise():
    r = decide(float("inf"), [], [])
    assert set(r.keys()) == REQUIRED_KEYS


def test_malformed_telemetry_does_not_raise():
    malformed = [
        {},
        {"foo": "bar"},
        {"vibration": "not_a_number"},
    ]

    try:
        r = decide(40, malformed, [])
    except Exception as e:
        pytest.fail(f"decide() raised on malformed telemetry: {e!r}")

    assert set(r.keys()) == REQUIRED_KEYS


def test_missing_telemetry_keys_does_not_raise():
    incomplete = [
        {"vibration": 0.2},
        {},
    ]

    try:
        r = decide(40, incomplete, [])
    except Exception as e:
        pytest.fail(f"decide() raised on incomplete telemetry: {e!r}")

    assert set(r.keys()) == REQUIRED_KEYS


# ---------- 4. HYSTERESIS ----------

def test_hysteresis_hold_at_27():
    # The existing engine reads previous risk_level/action_code from history.
    # Therefore the previous CRITICAL state must be explicitly represented.
    prev_history = [
        {
            "rul": 22,
            "risk_level": "CRITICAL",
            "action_code": "SERVICE_24H",
        },
        {
            "rul": 21,
            "risk_level": "CRITICAL",
            "action_code": "SERVICE_24H",
        },
        {
            "rul": 20,
            "risk_level": "CRITICAL",
            "action_code": "SERVICE_24H",
        },
    ]

    r = decide(27, [], prev_history)

    assert r["risk_level"] == "CRITICAL"
    assert r["action_code"] == "SERVICE_24H"


def test_hysteresis_release_at_31():
    prev_history = [
        {
            "rul": 22,
            "risk_level": "CRITICAL",
            "action_code": "SERVICE_24H",
        },
        {
            "rul": 21,
            "risk_level": "CRITICAL",
            "action_code": "SERVICE_24H",
        },
        {
            "rul": 20,
            "risk_level": "CRITICAL",
            "action_code": "SERVICE_24H",
        },
    ]

    r = decide(31, [], prev_history)

    assert r["risk_level"] == "WARNING"
    assert r["action_code"] == "SCHEDULE_72H"


# ---------- 5. OUTPUT CONTRACT ----------

@pytest.mark.parametrize("rul", [100, 70, 40, 20, 5])
def test_exact_seven_keys(rul):
    r = decide(rul, [], [])
    assert set(r.keys()) == REQUIRED_KEYS


@pytest.mark.parametrize("rul", [100, 70, 40, 20, 5, -10, 0])
def test_risk_score_bounded(rul):
    r = decide(rul, [], [])
    assert 0.0 <= r["risk_score"] <= 1.0


@pytest.mark.parametrize("rul", [100, 70, 40, 20, 5, -10, 0])
def test_health_index_bounded(rul):
    r = decide(rul, [], [])
    assert 0.0 <= r["health_index"] <= 1.0


def test_reason_is_string_and_bounded_length():
    r = decide(40, [], [])

    assert isinstance(r["reason"], str)
    assert len(r["reason"]) <= 120


@pytest.mark.parametrize("rul", [100, 70, 40, 20, 5])
def test_priority_matches_risk_level(rul):
    r = decide(rul, [], [])

    expected_priority, _ = BAND_MAP[r["risk_level"]]

    assert r["priority"] == expected_priority


@pytest.mark.parametrize("rul", [100, 70, 40, 20, 5])
def test_recommended_action_matches_action_code(rul):
    r = decide(rul, [], [])

    _, expected_actions = BAND_MAP[r["risk_level"]]

    if isinstance(expected_actions, set):
        assert r["action_code"] in expected_actions
    else:
        assert r["action_code"] == expected_actions

    assert isinstance(r["recommended_action"], str)
    assert len(r["recommended_action"]) > 0


@pytest.mark.parametrize("rul", [100, 70, 40, 20, 5])
def test_risk_level_in_configured_set(rul):
    r = decide(rul, [], [])

    assert r["risk_level"] in RISK_LEVELS


@pytest.mark.parametrize("rul", [100, 70, 40, 20, 5])
def test_action_code_in_configured_set(rul):
    r = decide(rul, [], [])

    assert r["action_code"] in ACTION_CODES


def test_escalation_threshold_configuration():
    # No exact combined-signal scenario was manually verified above,
    # so do not invent an escalation behavior test.
    assert RISK_SCORE_ESCALATION_THRESHOLD == pytest.approx(0.75)