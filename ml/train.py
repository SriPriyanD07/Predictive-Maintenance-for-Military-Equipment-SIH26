"""Train the RUL model on NASA C-MAPSS FD001. Runs end to end.

    python ml/train.py

Writes: model.pkl, model.json, metrics.json, rul_curve.png, sample_window.json
All paths resolve relative to this file, not the caller's cwd.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Running `python ml/train.py` puts ml/ on sys.path, not the repo root, so
# `from ml.features import ...` would fail. Same class of bug as Fix 3: never
# assume the caller's cwd or entry point. Must precede the ml.* imports below.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import joblib
import matplotlib

matplotlib.use("Agg")  # headless; no display on the demo machines
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import mean_absolute_error, mean_squared_error

from ml.features import build_features, FEATURE_NAMES
from ml.sensor_map import CONTRACT_KEYS, SENSOR_MAP, to_contract

_DIR = Path(__file__).resolve().parent
_ROOT = _DIR.parent

DATA = _ROOT / "data" / "CMaps" / "train_FD001.txt"
TEST = _ROOT / "data" / "CMaps" / "test_FD001.txt"
TEST_RUL = _ROOT / "data" / "CMaps" / "RUL_FD001.txt"

RUL_CAP = 125.0
WINDOW = 30
N_HOLDOUT = 20
SEED = 42

# P2 alert threshold. Lead time is measured as the first cycle where predicted
# RUL crosses below this, versus that unit's true end of life.
P2_THRESHOLD = 50

RAW_COLS = ["unit", "cycle", "op1", "op2", "op3"] + [f"s{i}" for i in range(1, 22)]


def load_raw(path):
    """Space-separated, no header. Trailing whitespace creates phantom empty
    columns, hence sep=r'\\s+' with index_col=False and an explicit width check."""
    df = pd.read_csv(path, sep=r"\s+", header=None, index_col=False)
    if df.shape[1] != 26:
        raise ValueError(f"expected 26 columns in {path}, got {df.shape[1]}")
    df.columns = RAW_COLS
    return df


def to_contract_frame(df):
    """Raw frame -> unit, cycle + the 7 contract channels (vibration rescaled)."""
    out = pd.DataFrame(
        {key: df[raw].astype(float) for raw, key in SENSOR_MAP.items()}
    )
    # rescale_vibration lives in to_contract; apply it channel-wise for speed
    from ml.sensor_map import rescale_vibration

    out["vibration"] = df["s11"].astype(float).map(rescale_vibration)
    out["unit"] = df["unit"].astype(int)
    out["cycle"] = df["cycle"].astype(int)
    return out[["unit", "cycle"] + CONTRACT_KEYS]


def add_labels(df):
    """RUL = unit_max_cycle - cycle, piecewise-linear, clipped at 125."""
    eol = df.groupby("unit")["cycle"].transform("max")
    df = df.copy()
    df["RUL"] = (eol - df["cycle"]).clip(upper=RUL_CAP).astype(float)
    return df


def windows_for_unit(unit_df):
    """Slide a 30-cycle window over one unit. Yields (features, label).

    Uses build_features -- the exact same function inference calls.
    """
    rows = unit_df.to_dict("records")
    for i in range(len(rows)):
        lo = max(0, i - WINDOW + 1)
        win = rows[lo : i + 1]
        yield build_features(win)[0], rows[i]["RUL"]


def build_training_matrix(df, units):
    X, y = [], []
    for u in units:
        sub = df[df["unit"] == u].sort_values("cycle")
        for feats, label in windows_for_unit(sub):
            X.append(feats)
            y.append(label)
    return np.asarray(X, dtype=float), np.asarray(y, dtype=float)


def main():
    if not DATA.exists():
        raise SystemExit(f"MISSING DATA: {DATA}")

    print("loading train_FD001 ...")
    raw = load_raw(DATA)
    df = add_labels(to_contract_frame(raw))

    all_units = np.array(sorted(df["unit"].unique()))
    rng = np.random.default_rng(SEED)
    holdout = np.sort(rng.choice(all_units, size=N_HOLDOUT, replace=False))
    train_units = np.array([u for u in all_units if u not in set(holdout.tolist())])

    print(f"units: {len(all_units)} total -> {len(train_units)} train, "
          f"{len(holdout)} held out for lead time")

    print("building training windows ...")
    X, y = build_training_matrix(df, train_units)
    print(f"training matrix: {X.shape}  ({len(FEATURE_NAMES)} features)")

    # NO FEATURE SCALER. XGBoost is invariant to monotonic scaling, and a
    # second artifact is a second thing that can fall out of sync at serve
    # time. [FIX 3, part b]
    print("training XGBRegressor ...")
    model = xgb.XGBRegressor(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.9,
        colsample_bytree=0.9,
        random_state=SEED,
        n_jobs=-1,
        tree_method="hist",
    )
    model.fit(X, y)

    # ---------------------------------------------------------- official test
    # Score on the OFFICIAL test set: each engine's LAST 30-cycle window,
    # against RUL_FD001.txt clipped at 125.
    print("scoring on official test set ...")
    test_raw = load_raw(TEST)
    test_df = to_contract_frame(test_raw)
    true_rul = pd.read_csv(TEST_RUL, sep=r"\s+", header=None, index_col=False)
    true_rul = true_rul.iloc[:, 0].astype(float).clip(upper=RUL_CAP).values

    preds = []
    for u in sorted(test_df["unit"].unique()):
        sub = test_df[test_df["unit"] == u].sort_values("cycle")
        win = sub.tail(WINDOW).to_dict("records")
        preds.append(float(model.predict(build_features(win))[0]))
    preds = np.clip(np.asarray(preds), 0.0, RUL_CAP)

    mae = float(mean_absolute_error(true_rul, preds))
    rmse = float(np.sqrt(mean_squared_error(true_rul, preds)))
    n_test = int(len(true_rul))

    # Baseline: predict mean training RUL for every engine.
    baseline_pred = float(np.mean(y))
    baseline_mae = float(mean_absolute_error(true_rul, np.full(n_test, baseline_pred)))

    # ------------------------------------------------------------- lead time
    # Measured on the 20 HELD-OUT TRAIN units, never on the test set.
    #
    # WHY: FD001 test engines are truncated at some point BEFORE failure, so
    # they have no observable end-of-life -- there is no true EOL cycle to
    # measure "cycles of warning before failure" against. Train units do run
    # all the way to failure, so their last cycle IS the real EOL. Held-out
    # units give an honest number: unseen during training, but complete.
    print("measuring lead time on held-out units ...")
    lead_times = []
    for u in holdout:
        sub = df[df["unit"] == u].sort_values("cycle")
        rows = sub.to_dict("records")
        eol = rows[-1]["cycle"]
        for i in range(len(rows)):
            lo = max(0, i - WINDOW + 1)
            p = float(model.predict(build_features(rows[lo : i + 1]))[0])
            if p < P2_THRESHOLD:
                lead_times.append(eol - rows[i]["cycle"])
                break
    lead_time = float(np.median(lead_times)) if lead_times else 0.0

    # ------------------------------------------------------------- artifacts
    joblib.dump(model, _DIR / "model.pkl")           # model object ONLY
    model.save_model(str(_DIR / "model.json"))        # version-portable backup

    metrics = {
        "model": "XGBoost",
        "dataset": "NASA C-MAPSS FD001",
        "mae": round(mae, 3),
        "rmse": round(rmse, 3),
        "n_test": n_test,
        "baseline_mae": round(baseline_mae, 3),
        "lead_time_cycles": round(lead_time, 1),
        "trained_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    (_DIR / "metrics.json").write_text(json.dumps(metrics, indent=2))

    # RUL curve for the pitch deck: one held-out engine, predicted vs actual.
    demo_unit = int(holdout[0])
    sub = df[df["unit"] == demo_unit].sort_values("cycle")
    rows = sub.to_dict("records")
    pred_curve = []
    for i in range(len(rows)):
        lo = max(0, i - WINDOW + 1)
        pred_curve.append(float(model.predict(build_features(rows[lo : i + 1]))[0]))
    plt.figure(figsize=(9, 5))
    plt.plot(sub["cycle"], sub["RUL"], label="actual RUL", linewidth=2)
    plt.plot(sub["cycle"], pred_curve, label="predicted RUL", linewidth=2)
    plt.axhline(RUL_CAP, linestyle="--", color="grey", label="cap (125)")
    plt.xlabel("cycle")
    plt.ylabel("RUL")
    plt.title(f"Held-out engine {demo_unit}: predicted vs actual RUL")
    plt.legend()
    plt.tight_layout()
    plt.savefig(_DIR / "rul_curve.png", dpi=130)
    plt.close()

    # 30 consecutive readings in exact contract dict format.
    sample_rows = sub.head(WINDOW)
    sample = [
        {**to_contract_from_contract_row(r), "cycle": int(r["cycle"])}
        for r in sample_rows.to_dict("records")
    ]
    (_DIR / "sample_window.json").write_text(json.dumps(sample, indent=2))

    # ------------------------------------------------------------- summary
    print()
    print("=" * 52)
    print(f"{'metric':<22}{'value':>28}")
    print("-" * 52)
    for k, v in metrics.items():
        print(f"{k:<22}{str(v):>28}")
    print("=" * 52)
    print(f"lead-time units used: {len(lead_times)}/{N_HOLDOUT}")
    if mae > 25:
        print("\n!! MAE > 25 -- reporting rather than tuning, as instructed.")
    print(f"\nartifacts written to {_DIR}")


def to_contract_from_contract_row(row):
    """Row is already in contract space; just pull the 7 keys as floats."""
    return {k: float(row[k]) for k in CONTRACT_KEYS}


if __name__ == "__main__":
    main()
