"""SINGLE SOURCE OF TRUTH for C-MAPSS -> contract translation.

M5 imports this module. Do not duplicate these constants anywhere else.

FIX 1 (train/serve skew): vibration is served to the UI on a g-force-looking
0.2-1.4 scale, but raw C-MAPSS s11 sits around 47. If the model trains on raw
s11 while the simulator serves rescaled values, every tree split lands at a
threshold no incoming value ever crosses and the model silently returns a
near-constant RUL. No exception, no traceback -- just a dead demo. So training
applies rescale_vibration() too, and train/serve see identical distributions.
"""

# NO third-party imports. backend/fallbacks.py imports this module, and that
# module has to keep working on a machine where the ML stack (numpy, xgboost)
# was never pip installed -- that is the entire reason fallbacks.py exists.

# ---------------------------------------------------------------- mapping ---

# raw C-MAPSS sensor column -> frozen contract key
SENSOR_MAP = {
    "s2": "core_temp",
    "s3": "exhaust_temp",
    "s4": "pressure",
    "s7": "fuel_flow",
    "s11": "vibration",
    "s12": "fan_speed",
    "s15": "core_speed",
}

# Fixed order. Feature columns are built from this every time so ordering can
# never drift between training and inference.
CONTRACT_KEYS = [
    "core_temp",
    "exhaust_temp",
    "fan_speed",
    "core_speed",
    "pressure",
    "vibration",
    "fuel_flow",
]

# reverse lookup: contract key -> raw column
CONTRACT_TO_RAW = {v: k for k, v in SENSOR_MAP.items()}

# ------------------------------------------------------------- vibration ---

# Measured from train_FD001.txt in Step 1. Hardcoded deliberately: inference
# must not depend on the training file being present on disk.
VIB_RAW_MIN = 46.85
VIB_RAW_MAX = 48.53

VIB_OUT_MIN = 0.2
VIB_OUT_MAX = 1.4


def rescale_vibration(raw_s11):
    """Min-max raw s11 into the 0.2-1.4 display scale.

    The normalised fraction is clipped to [0, 1] so inference values outside
    the training range cannot produce out-of-band output.
    """
    raw = float(raw_s11)
    span = VIB_RAW_MAX - VIB_RAW_MIN
    if span <= 0:  # degenerate guard; never true for FD001
        return float(VIB_OUT_MIN)
    frac = (raw - VIB_RAW_MIN) / span
    frac = max(0.0, min(1.0, frac))
    return float(VIB_OUT_MIN + frac * (VIB_OUT_MAX - VIB_OUT_MIN))


# -------------------------------------------------------------- contract ---


# ----------------------------------------------- nominal / degradation ---
#
# THE canonical telemetry constants. backend/fallbacks.py and ml/model.py both
# import these -- nobody hand-writes "realistic-looking" jet engine numbers
# anywhere else. Values that look physically odd (core_speed ~8.4 rather than
# thousands of RPM) are correct: SENSOR_MAP gives raw C-MAPSS channels
# physically-suggestive names, but s15 is a bypass ratio, not an RPM. The model
# only ever saw these ranges, so anything outside them produces a constant,
# wrong RUL with no error.
#
# All three dicts measured from train_FD001 (see tools/check_skew.py).

# Median of cycles 1-5: a healthy, just-installed unit.
BASELINE = {
    "core_temp": 642.38,
    "exhaust_temp": 1587.24,
    "fan_speed": 521.94,
    "core_speed": 8.42,
    "pressure": 1402.92,
    "vibration": 0.557,
    "fuel_flow": 553.99,
}

# Full observed range per channel; used to normalise deviation from BASELINE.
SPREAD = {
    "core_temp": 3.32,
    "exhaust_temp": 45.87,
    "fan_speed": 4.69,
    "core_speed": 0.26,
    "pressure": 59.24,
    "vibration": 1.20,
    "fuel_flow": 6.21,
}

# Channels whose value FALLS as the unit degrades (mean at RUL>=120 vs RUL<=10).
# Measured, not assumed: core_speed and pressure both RISE with degradation,
# and fuel_flow falls -- the reverse of what the channel names suggest.
DECREASING = {"fan_speed", "fuel_flow"}

# Signed movement from healthy to failed: mean(RUL>=120) -> mean(RUL<=10).
# Anything generating synthetic telemetry should sweep BASELINE -> BASELINE+DELTA
# as a unit degrades. Using these keeps generated values inside the range the
# model was trained on, which is the whole point.
DELTA = {
    "core_temp": +1.181,
    "exhaust_temp": +14.038,
    "fan_speed": -1.917,
    "core_speed": +0.094,
    "pressure": +23.836,
    "vibration": +0.516,
    "fuel_flow": -2.258,
}


def to_contract(row):
    """One raw C-MAPSS row -> dict of the 7 contract keys, all float.

    Accepts anything indexable by raw column name (pandas Series, dict).
    Vibration is rescaled here so callers cannot forget to.
    """
    out = {}
    for raw_col, key in SENSOR_MAP.items():
        val = row[raw_col]
        if key == "vibration":
            out[key] = rescale_vibration(val)
        else:
            out[key] = float(val)
    return out
