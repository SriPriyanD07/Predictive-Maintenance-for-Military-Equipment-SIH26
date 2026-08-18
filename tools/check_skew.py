"""Checkpoint 1 tool: compare the live simulator's output distribution against
what the model actually trained on.

    python tools/check_skew.py

This is the early-warning system for FIX 1. If M5's simulator emits a channel
on a different scale than training saw, XGBoost's split thresholds sit where no
incoming value ever lands and RUL flatlines -- silently, with no traceback.
Run this the moment the simulator exists.
"""

import sys
from pathlib import Path

import numpy as np

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ml.sensor_map import CONTRACT_KEYS, SENSOR_MAP, rescale_vibration

N_TICKS = 200


def training_stats():
    """min/max/mean per contract channel, from train_FD001 in contract space."""
    import pandas as pd

    path = _ROOT / "data" / "CMaps" / "train_FD001.txt"
    if not path.exists():
        return None
    cols = ["unit", "cycle", "op1", "op2", "op3"] + [f"s{i}" for i in range(1, 22)]
    df = pd.read_csv(path, sep=r"\s+", header=None, index_col=False)
    df.columns = cols

    stats = {}
    for raw, key in SENSOR_MAP.items():
        s = df[raw].astype(float)
        if key == "vibration":
            s = s.map(rescale_vibration)
        stats[key] = (float(s.min()), float(s.max()), float(s.mean()))
    return stats


def _find_simulator(use_fallback=False):
    """Locate a simulator class. Returns (instance, label) or (None, None).

    M5's module does not exist yet, so shape is not assumed: the class may be
    called Simulator or FallbackSimulator, and the tick method may be tick(),
    step() or next(). Falls back to backend.fallbacks.FallbackSimulator, which
    is a real working simulator with the same output shape -- that is what lets
    this branch be exercised before M5's code lands.
    """
    candidates = []
    if not use_fallback:
        candidates.append(("sim.simulator", ("Simulator", "FallbackSimulator")))
    candidates.append(("backend.fallbacks", ("FallbackSimulator", "Simulator")))

    for modname, classnames in candidates:
        try:
            mod = __import__(modname, fromlist=["*"])
        except Exception:  # noqa: BLE001
            continue
        for cn in classnames:
            cls = getattr(mod, cn, None)
            if cls is None:
                continue
            try:
                inst = cls()
            except Exception:  # noqa: BLE001
                continue
            label = f"{modname}.{cn}"
            return inst, label
    return None, None


def _tick(sim):
    """Call whatever this simulator calls its advance method."""
    for name in ("tick", "step", "next", "advance"):
        fn = getattr(sim, name, None)
        if callable(fn):
            return fn()
    raise AttributeError("simulator has no tick/step/next/advance method")


def _units_of(state):
    """Unwrap a tick's return value into a list of per-unit dicts.

    Handles: bare list, {"units": [...]}, {"fleet": [...]}, single dict.
    """
    if state is None:
        return []
    if isinstance(state, list):
        return state
    if isinstance(state, dict):
        for key in ("units", "fleet", "state"):
            v = state.get(key)
            if isinstance(v, list):
                return v
        # a single unit dict
        if any(k in state for k in CONTRACT_KEYS):
            return [state]
    return []


def _telemetry_of(unit):
    """Pull the 7 channels whether they are flat or nested under 'telemetry'."""
    if not isinstance(unit, dict):
        return {}
    nested = unit.get("telemetry")
    if isinstance(nested, dict) and any(k in nested for k in CONTRACT_KEYS):
        return nested
    return unit


def simulator_stats(use_fallback=False):
    """min/max/mean per contract channel, from the live simulator."""
    sim, label = _find_simulator(use_fallback)
    if sim is None:
        return None, None

    seen = {k: [] for k in CONTRACT_KEYS}
    for _ in range(N_TICKS):
        for u in _units_of(_tick(sim)):
            tel = _telemetry_of(u)
            for k in CONTRACT_KEYS:
                if k in tel:
                    try:
                        seen[k].append(float(tel[k]))
                    except (TypeError, ValueError):
                        pass

    stats = {}
    for k, vals in seen.items():
        if vals:
            a = np.asarray(vals)
            stats[k] = (float(a.min()), float(a.max()), float(a.mean()))
    return (stats or None), label


def main():
    use_fallback = "--fallback" in sys.argv
    train = training_stats()
    sim, label = simulator_stats(use_fallback)

    if train is None:
        print("training data not found -- cannot show the reference distribution")

    if sim is None:
        print()
        print("=" * 64)
        print("  M5's simulator not available yet (no importable sim.simulator).")
        print("  Re-run this at Checkpoint 1, once the simulator lands.")
        print("=" * 64)
    else:
        print(f"\nsimulator source: {label}  ({N_TICKS} ticks)")

    skewed = []
    if train:
        print()
        print(f"{'channel':<14}{'source':<8}{'min':>12}{'max':>12}{'mean':>12}")
        print("-" * 64)
        for k in CONTRACT_KEYS:
            lo, hi, mu = train[k]
            print(f"{k:<14}{'train':<8}{lo:>12.3f}{hi:>12.3f}{mu:>12.3f}")
            if sim and k in sim:
                slo, shi, smu = sim[k]
                print(f"{'':<14}{'sim':<8}{slo:>12.3f}{shi:>12.3f}{smu:>12.3f}")
                # Flag any channel whose live mean falls outside the training
                # range -- that is the skew that kills the demo.
                if not (lo <= smu <= hi):
                    skewed.append(k)
                    print(f"{'':<14}{'!! SKEW':<8}  sim mean {smu:.3f} is outside "
                          f"training range [{lo:.3f}, {hi:.3f}]")
            print()

    if sim is not None:
        print("-" * 64)
        if skewed:
            print(f"RESULT: {len(skewed)}/{len(CONTRACT_KEYS)} channels SKEWED -> "
                  f"{', '.join(skewed)}")
            print("The model will return a near-constant RUL for these. Fix the")
            print("generator to sweep BASELINE -> BASELINE+DELTA from ml/sensor_map.py.")
            return 1
        print(f"RESULT: all {len(CONTRACT_KEYS)} channels within training range.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
