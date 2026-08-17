"""Feature construction, shared by training and inference.

build_features() is called by BOTH ml/train.py and ml/model.py. That is the
whole point: one code path means zero train/serve skew. If you change anything
here, retrain -- do not special-case inference.

Windows are short at simulation start (often length 1), so every rolling
statistic uses min_periods=1 and every span degrades gracefully.
"""

import numpy as np

from ml.sensor_map import CONTRACT_KEYS

# Rolling spans, in cycles.
SPANS = (5, 20)


def _feature_names():
    """Fixed column order. Built once, at import, from CONTRACT_KEYS."""
    names = []
    for key in CONTRACT_KEYS:
        names.append(f"{key}")
        for span in SPANS:
            names.append(f"{key}_mean{span}")
            names.append(f"{key}_std{span}")
            names.append(f"{key}_delta{span}")
    names.append("cycle")
    return names


# Module-level FIXED order. The feature array is assembled from this list every
# single time, so column ordering can never drift between train and serve.
FEATURE_NAMES = _feature_names()
N_FEATURES = len(FEATURE_NAMES)


def _safe_series(window, key):
    """Extract one channel from the window as a float array.

    Missing keys, None, NaN and non-numeric junk all collapse to 0.0 rather
    than raising -- predict_rul must never blow up on malformed input.
    """
    vals = []
    for row in window:
        try:
            v = float(row.get(key, 0.0))
        except (TypeError, ValueError, AttributeError):
            v = 0.0
        if not np.isfinite(v):
            v = 0.0
        vals.append(v)
    if not vals:
        vals = [0.0]
    return np.asarray(vals, dtype=float)


def build_features(window):
    """window: list[dict] oldest->newest, each with the 7 contract keys + cycle.

    Returns np.ndarray shape (1, N_FEATURES), columns ordered by FEATURE_NAMES.
    """
    if not window:
        window = [{}]

    feats = {}

    for key in CONTRACT_KEYS:
        arr = _safe_series(window, key)
        cur = arr[-1]
        feats[key] = cur

        for span in SPANS:
            # min_periods=1 semantics: use whatever we have, up to `span`.
            tail = arr[-span:] if len(arr) >= 1 else np.array([0.0])
            feats[f"{key}_mean{span}"] = float(np.mean(tail))
            # std of a single sample is 0.0, not NaN
            feats[f"{key}_std{span}"] = float(np.std(tail)) if len(tail) > 1 else 0.0
            # delta over the span: current minus the value `span` cycles back,
            # falling back to the oldest value we actually have
            if len(arr) > span:
                ref = arr[-(span + 1)]
            else:
                ref = arr[0]
            feats[f"{key}_delta{span}"] = float(cur - ref)

    # cycle comes from the newest row
    try:
        cyc = float(window[-1].get("cycle", 0.0))
    except (TypeError, ValueError, AttributeError):
        cyc = 0.0
    if not np.isfinite(cyc):
        cyc = 0.0
    feats["cycle"] = cyc

    # Assemble strictly in FEATURE_NAMES order.
    vec = np.array([[feats[name] for name in FEATURE_NAMES]], dtype=float)
    vec = np.nan_to_num(vec, nan=0.0, posinf=0.0, neginf=0.0)
    return vec
