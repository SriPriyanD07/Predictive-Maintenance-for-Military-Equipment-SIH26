"""SINGLE SOURCE OF TRUTH for C-MAPSS -> contract translation.

M5 imports this module. Do not duplicate these constants anywhere else.

FIX 1 (train/serve skew): vibration is served to the UI on a g-force-looking
0.2-1.4 scale, but raw C-MAPSS s11 sits around 47. If the model trains on raw
s11 while the simulator serves rescaled values, every tree split lands at a
threshold no incoming value ever crosses and the model silently returns a
near-constant RUL. No exception, no traceback -- just a dead demo. So training
applies rescale_vibration() too, and train/serve see identical distributions.
"""

import numpy as np

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
    frac = float(np.clip(frac, 0.0, 1.0))
    return float(VIB_OUT_MIN + frac * (VIB_OUT_MAX - VIB_OUT_MIN))


# -------------------------------------------------------------- contract ---


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
