"""Public inference interface. Imported by the backend.

    from ml.model import predict_rul, load_model, BASELINE

FIX 3 (path resolution): a default of "ml/model.pkl" resolves against the
CALLER's working directory. M3 launches uvicorn from the repo root; others
launch from elsewhere; pytest launches from wherever it feels like. Every path
here is anchored to __file__, so the module works from any cwd on any machine.

predict_rul() MUST NEVER RAISE. Every failure path degrades to a usable number.
"""

import json
import logging
import sys
import time
from pathlib import Path

import numpy as np

_DIR = Path(__file__).resolve().parent
_ROOT = _DIR.parent

# Allow `python ml/model.py` to resolve `ml.features` (running a file directly
# puts ml/ on sys.path, not the repo root).
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ml.features import build_features
from ml.sensor_map import CONTRACT_KEYS

log = logging.getLogger(__name__)

RUL_CAP = 125.0
SENTINEL = (125.0, 100.0, 125.0)   # returned on empty/corrupt input
DEFAULT_MAE = 25.0                  # band width if metrics.json is unreadable

# Nominal healthy telemetry, in CONTRACT SPACE (median of cycles 1-5 across
# train_FD001, vibration already rescaled). The backend seeds initial unit
# state from this, so it must sit in the same distribution the model trained
# on -- see the scale-mismatch note in the M1 handoff.
BASELINE = {
    "core_temp": 642.38,
    "exhaust_temp": 1587.24,
    "fan_speed": 521.94,
    "core_speed": 8.42,
    "pressure": 1402.92,
    "vibration": 0.557,
    "fuel_flow": 553.99,
}

# ------------------------------------------------------------- singleton ---

_MODEL = None
_MODEL_TRIED = False
_MISSING_LOGGED = False
_MAE = None


def _resolve(path):
    """None -> ml/model.pkl. Relative -> against REPO ROOT, never cwd."""
    if path is None:
        return _DIR / "model.pkl"
    p = Path(path)
    return p if p.is_absolute() else (_ROOT / p)


def load_model(path=None):
    """Load and cache the model. Returns the model object, or None.

    joblib first; on ANY failure fall back to XGBoost's native JSON format,
    which survives a version mismatch between teammates' installs.
    """
    global _MODEL, _MODEL_TRIED, _MISSING_LOGGED
    _MODEL_TRIED = True

    pkl = _resolve(path)
    try:
        import joblib

        _MODEL = joblib.load(pkl)
        return _MODEL
    except Exception as exc:  # noqa: BLE001 - any failure falls through
        log.debug("joblib load failed for %s: %s", pkl, exc)

    try:
        import xgboost as xgb

        js = pkl.with_suffix(".json") if pkl.suffix == ".pkl" else _DIR / "model.json"
        if js.exists():
            m = xgb.XGBRegressor()
            m.load_model(str(js))
            _MODEL = m
            log.warning("loaded model from %s (joblib path failed)", js)
            return _MODEL
    except Exception as exc:  # noqa: BLE001
        log.debug("xgboost json load failed: %s", exc)

    _MODEL = None
    if not _MISSING_LOGGED:
        log.warning(
            "no model artifact found (looked for %s and model.json); "
            "falling back to the cycle heuristic", pkl
        )
        _MISSING_LOGGED = True
    return None


def _get_model():
    if not _MODEL_TRIED:
        load_model()
    return _MODEL


def _get_mae():
    """Half-width of the uncertainty band, read once from metrics.json."""
    global _MAE
    if _MAE is None:
        try:
            _MAE = float(json.loads((_DIR / "metrics.json").read_text())["mae"])
        except Exception:  # noqa: BLE001
            _MAE = DEFAULT_MAE
    return _MAE


# ------------------------------------------------------------- inference ---


def _valid(window):
    """Reject empty/corrupt windows so they hit the sentinel, not the model."""
    if not window:
        return False
    last = window[-1]
    if not isinstance(last, dict) or not last:
        return False
    return all(k in last for k in CONTRACT_KEYS)


def _heuristic(window):
    """No-model fallback: the Step 0 stub curve."""
    try:
        c = float(window[-1].get("cycle", 0.0))
    except Exception:  # noqa: BLE001
        c = 0.0
    return max(0.0, RUL_CAP - c * 0.55)


def predict_rul(window):
    """window: list[dict] oldest->newest, 1..30 long, 7 contract keys + cycle.

    Returns (rul, low, high), rul clipped to [0, 125]. Never raises.
    """
    try:
        if not _valid(window):
            return SENTINEL

        model = _get_model()
        if model is None:
            rul = _heuristic(window)
        else:
            rul = float(model.predict(build_features(window))[0])

        if not np.isfinite(rul):
            return SENTINEL

        rul = float(np.clip(rul, 0.0, RUL_CAP))
        mae = _get_mae()
        low = float(np.clip(rul - mae, 0.0, RUL_CAP))
        high = float(np.clip(rul + mae, 0.0, RUL_CAP))
        return (rul, low, high)
    except Exception:  # noqa: BLE001 - contract: never raise
        return SENTINEL


# ------------------------------------------------------------------ main ---

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    t0 = time.perf_counter()
    load_model()
    t_load = (time.perf_counter() - t0) * 1000
    print(f"load_model(): {t_load:.1f} ms  -> {type(_MODEL).__name__}")

    sample = json.loads((_DIR / "sample_window.json").read_text())
    print(f"sample_window.json: {len(sample)} readings")

    for n in (1, 3, 30):
        win = sample[:n]
        t0 = time.perf_counter()
        out = predict_rul(win)
        dt = (time.perf_counter() - t0) * 1000
        print(f"  len={n:<3} -> rul={out[0]:7.2f}  band=({out[1]:.2f}, {out[2]:.2f})"
              f"   {dt:.2f} ms")
