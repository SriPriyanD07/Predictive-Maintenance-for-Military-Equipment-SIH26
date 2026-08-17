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


def simulator_stats():
    """min/max/mean per contract channel, from M5's live simulator."""
    try:
        from sim.simulator import Simulator
    except Exception:  # noqa: BLE001
        return None

    sim = Simulator()
    seen = {k: [] for k in CONTRACT_KEYS}
    for _ in range(N_TICKS):
        state = sim.tick()
        units = state if isinstance(state, list) else state.get("units", [])
        for u in units:
            tel = u.get("telemetry", u)
            for k in CONTRACT_KEYS:
                if k in tel:
                    seen[k].append(float(tel[k]))

    stats = {}
    for k, vals in seen.items():
        if vals:
            a = np.asarray(vals)
            stats[k] = (float(a.min()), float(a.max()), float(a.mean()))
    return stats


def main():
    train = training_stats()
    sim = simulator_stats()

    if train is None:
        print("training data not found -- cannot show the reference distribution")

    if sim is None:
        print()
        print("=" * 64)
        print("  M5's simulator not available yet (no importable sim.simulator).")
        print("  Re-run this at Checkpoint 1, once the simulator lands.")
        print("=" * 64)

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
                    print(f"{'':<14}{'!! SKEW':<8}  sim mean {smu:.3f} is outside "
                          f"training range [{lo:.3f}, {hi:.3f}]")
            print()


if __name__ == "__main__":
    main()
