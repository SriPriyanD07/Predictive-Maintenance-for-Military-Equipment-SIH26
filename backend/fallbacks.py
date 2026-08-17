import math
import random
import sys
from pathlib import Path
import pickle

# ============================================================
# sim/simulator.py  (Simulator -> FallbackSimulator)
# ============================================================

TELEMETRY_KEYS = (
    "core_temp", "exhaust_temp", "fan_speed", "core_speed",
    "pressure", "vibration", "fuel_flow",
)

# unit_id, unit_name, start-cycle offset (cycles already accumulated before tick 0),
# degradation-rate multiplier (cycles accrued per simulator tick),
# severity: amplitude of the telemetry excursion, as a multiple of DELTA.
#
# Why severity exists: DELTA is the MEAN healthy->failed movement across all 100
# training engines, so a unit that sweeps exactly BASELINE -> BASELINE+DELTA
# lands at the average failure condition -- which the model scores at RUL 15.6,
# just above the 15.0 CRITICAL threshold. Rate alone cannot fix that; it moves a
# unit faster along a curve that still saturates at the same place. Severity
# lets the hero unit degrade past the average, the way a genuinely bad engine
# does, so the demo actually reaches CRITICAL.
_UNIT_CONFIGS = (
    ("M-011", "Turbofan Engine 011", 10, 0.5, 0.8),
    ("M-014", "Turbofan Engine 014", 40, 0.5, 0.9),
    ("M-017", "Turbofan Engine 017", 95, 1.0, 1.2),   # hero unit
    ("M-021", "Turbofan Engine 021", 5, 0.5, 0.7),
    ("M-023", "Turbofan Engine 023", 130, 0.5, 1.1),
    ("M-029", "Turbofan Engine 029", 0, 0.5, 0.6),
)

# Degradation curve: logistic, saturates toward but never reaches 1.0, so RUL
# approaches but never flatlines exactly at 0. MID/SCALE are tuned so the hero
# unit (M-017) tracks the demo arc: WATCH at tick 1, WARNING around tick
# 60-90, CRITICAL between tick 140-170.
DEGRADATION_MID = 130.0
DEGRADATION_SCALE = 65.0

_SEED = 42


def _degradation(cycle):
    return 1.0 / (1.0 + math.exp(-(cycle - DEGRADATION_MID) / DEGRADATION_SCALE))


class FallbackSimulator:
    def __init__(self, scenario="default"):
        self.scenario = scenario
        self._tick_index = 0
        self._rng = random.Random(_SEED)
        self.units = [
            {"unit_id": uid, "unit_name": name, "offset": offset, "rate": rate,
             "severity": severity}
            for uid, name, offset, rate, severity in _UNIT_CONFIGS
        ]

    @property
    def tick_index(self):
        return self._tick_index

    def reset(self):
        self._tick_index = 0
        self._rng = random.Random(_SEED)

    def tick(self):
        self._tick_index += 1
        out = []
        for u in self.units:
            cycle = u["offset"] + self._tick_index * u["rate"]
            degradation = _degradation(cycle)
            n = lambda scale: self._rng.uniform(-scale, scale)
            # Telemetry sweeps BASELINE -> BASELINE+DELTA as the unit degrades,
            # all from ml/sensor_map.py. These used to be inline literals
            # (core_speed 9000, pressure 14.5) taken from s8/s9 -- the real
            # physical speed sensors -- but the frozen contract maps
            # core_speed->s15 (a bypass ratio) and fan_speed->s12 (a flow
            # ratio). Correct physics, wrong sensors for this contract: 6 of 7
            # channels landed outside the model's training range, so RUL came
            # back near-constant with no error.
            severity = u.get("severity", 1.0)
            telemetry = {
                key: round(
                    BASELINE[key]
                    + degradation * severity * DELTA[key]
                    + n(abs(DELTA[key]) * 0.15),
                    4,
                )
                for key in CONTRACT_KEYS
            }
            out.append({
                "unit_id": u["unit_id"],
                "unit_name": u["unit_name"],
                "cycle": int(round(cycle)),
                **telemetry,
            })
        return out

    def jump(self, tick):
        while self._tick_index < tick:
            self.tick()


# ============================================================
# ml/model.py  (predict_rul -> fallback_predict_rul)
# ============================================================

# Telemetry constants come from ml/sensor_map.py -- the single source of truth.
# The dicts that used to live here held invented "realistic-looking" jet engine
# numbers (core_speed 9000, pressure 14.5) chosen before the C-MAPSS contract
# existed. Five of seven were outside the range the model ever trained on, and
# the degradation directions were backwards on three, so the fallback heuristic
# and the model disagreed about which way "worse" is. Do not re-add literals.
#
# sensor_map has no third-party imports, so this works even where the ML stack
# was never installed.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ml.sensor_map import (  # noqa: E402
    BASELINE,
    CONTRACT_KEYS,
    DECREASING as _DECREASING,
    DELTA,
    SPREAD as _SPREAD,
    VIB_OUT_MAX,
    VIB_OUT_MIN,
)

# Relative importance per channel in the composite health score. Stays local:
# this is a heuristic tuning knob, not a property of the data.
_WEIGHT = {
    "core_temp": 1.0,
    "exhaust_temp": 1.3,
    "fan_speed": 0.8,
    "core_speed": 0.8,
    "pressure": 0.9,
    "vibration": 1.3,
    "fuel_flow": 0.9,
}

_MODEL = None
MODEL_LOADED = False


def load_model(path="ml/model.pkl"):
    global _MODEL, MODEL_LOADED
    try:
        p = Path(path)
        if not p.exists():
            _MODEL = None
            MODEL_LOADED = False
            return None
        with open(p, "rb") as f:
            _MODEL = pickle.load(f)
        MODEL_LOADED = True
        return _MODEL
    except Exception:
        _MODEL = None
        MODEL_LOADED = False
        return None


def _heuristic(window):
    latest = window[-1]
    composite = 0.0
    wsum = 0.0
    for key, base in BASELINE.items():
        spread = _SPREAD[key]
        val = float(latest.get(key, base))
        if key in _DECREASING:
            dev = (base - val) / spread
        else:
            dev = (val - base) / spread
        dev = max(0.0, min(1.3, dev))
        weight = _WEIGHT[key]
        composite += dev * weight
        wsum += weight
    composite = composite / wsum if wsum else 0.0
    health_frac = max(0.0, min(1.0, 1.0 - composite))
    rul = health_frac * 125.0
    confidence = min(len(window) / 30.0, 1.0)
    band = 20.0 - 10.0 * confidence
    low = max(0.0, rul - band)
    high = min(125.0, rul + band)
    return (round(rul, 2), round(low, 2), round(high, 2))


def _with_model(window):
    # Order from CONTRACT_KEYS, not dict iteration order -- feature column
    # order must not depend on how a dict happens to be written.
    features = [float(window[-1].get(k, BASELINE[k])) for k in CONTRACT_KEYS]
    rul = float(_MODEL.predict([features])[0])
    rul = max(0.0, min(125.0, rul))
    low = max(0.0, rul - 12.0)
    high = min(125.0, rul + 12.0)
    return (round(rul, 2), round(low, 2), round(high, 2))


def fallback_predict_rul(window):
    try:
        if not window:
            return (125.0, 110.0, 125.0)
        if _MODEL is not None:
            try:
                return _with_model(window)
            except Exception:
                pass
        return _heuristic(window)
    except Exception:
        return (60.0, 40.0, 80.0)


# ============================================================
# decision/engine.py  (decide -> fallback_decide)
# ============================================================

DEADBAND = 8.0

_LEVELS = ("NOMINAL", "WATCH", "WARNING", "CRITICAL")
_LEVEL_INDEX = {name: i for i, name in enumerate(_LEVELS)}
_PRIORITIES = ("P4", "P3", "P2", "P1")

THRESHOLDS = {
    "WATCH": 80.0,
    "WARNING": 50.0,
    "CRITICAL": 15.0,
}

_RECOMMENDED_ACTION = {
    "MONITOR": "Continue normal operation, monitor telemetry",
    "INSPECT_7D": "Schedule inspection within 7 days",
    "SCHEDULE_72H": "Schedule maintenance within 72 hours",
    "SERVICE_24H": "Service required within 24 hours",
    "GROUND_NOW": "Ground unit immediately for service",
}

_SAFE_DEFAULT = {
    "health_index": 1.0,
    "risk_score": 0.0,
    "risk_level": "NOMINAL",
    "priority": "P4",
    "action_code": "MONITOR",
    "recommended_action": _RECOMMENDED_ACTION["MONITOR"],
    "reason": "Default safe state: insufficient data for assessment",
}


def _raw_level_index(rul):
    if rul < THRESHOLDS["CRITICAL"]:
        return 3
    if rul < THRESHOLDS["WARNING"]:
        return 2
    if rul < THRESHOLDS["WATCH"]:
        return 1
    return 0


def _boundary_for(level_index):
    if level_index == 1:
        return THRESHOLDS["WATCH"]
    if level_index == 2:
        return THRESHOLDS["WARNING"]
    if level_index == 3:
        return THRESHOLDS["CRITICAL"]
    return None


def _latch_level(rul, prev_index):
    raw = _raw_level_index(rul)
    if raw > prev_index:
        return raw
    if raw < prev_index:
        boundary = _boundary_for(prev_index)
        if boundary is not None and rul >= boundary + DEADBAND:
            return prev_index - 1
        return prev_index
    return prev_index


def fallback_decide(rul, window, history):
    try:
        rul_c = max(0.0, min(125.0, float(rul)))
        latest = window[-1] if window else {}
        # Normalise against the real serving range (VIB_OUT_MIN..VIB_OUT_MAX),
        # not the old hardcoded 0.3/2.5 which capped vib_norm at 0.44 and so
        # silently understated 30% of the risk score.
        vibration = float(latest.get("vibration", BASELINE["vibration"]))
        _vib_span = VIB_OUT_MAX - VIB_OUT_MIN
        vib_norm = max(0.0, min(1.0, (vibration - VIB_OUT_MIN) / _vib_span))
        health_index = max(0.0, min(1.0, rul_c / 125.0))
        risk_score = max(0.0, min(1.0, 0.7 * (1.0 - health_index) + 0.3 * vib_norm))

        if history:
            prev_level = history[-1].get("risk_level", "NOMINAL")
            prev_index = _LEVEL_INDEX.get(prev_level, _raw_level_index(rul_c))
        else:
            prev_index = _raw_level_index(rul_c)

        level_index = _latch_level(rul_c, prev_index)
        risk_level = _LEVELS[level_index]
        priority = _PRIORITIES[level_index]

        if level_index == 0:
            action_code = "MONITOR"
        elif level_index == 1:
            action_code = "INSPECT_7D"
        elif level_index == 2:
            action_code = "SCHEDULE_72H" if rul_c >= 30.0 else "SERVICE_24H"
        else:
            action_code = "GROUND_NOW"

        recommended_action = _RECOMMENDED_ACTION[action_code]
        reason = f"RUL {rul_c:.1f} cycles, risk {risk_score:.2f}, vibration {vibration:.2f}"

        return {
            "health_index": round(health_index, 3),
            "risk_score": round(risk_score, 3),
            "risk_level": risk_level,
            "priority": priority,
            "action_code": action_code,
            "recommended_action": recommended_action[:60],
            "reason": reason[:120],
        }
    except Exception:
        return dict(_SAFE_DEFAULT)
