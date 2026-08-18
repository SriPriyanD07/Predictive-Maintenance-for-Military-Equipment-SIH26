"""
build_scenario.py

Builds data/scenarios/default.csv: a long-format telemetry replay scenario
derived from NASA C-MAPSS FD001, for the hackathon PoC simulator.

WHAT THIS SCRIPT DOES
----------------------
1. Reads data/CMaps/train_FD001.txt (space-separated, no header):
   columns = unit, cycle, op1, op2, op3, s1..s21  (26 columns)

2. Selects 6 engines whose total lifespan (max cycle count) is closest to
   the target lifespans [128, 156, 189, 206, 231, 287]. Selection is
   data-driven (nearest match by absolute difference in max cycle),
   not hardcoded.

3. Converts each selected engine's raw sensors to the project's frozen
   telemetry contract using ml.sensor_map.to_contract(), which is the
   single source of truth (per ml/sensor_map.py) for:
     - which raw sensors map to which contract keys
       (s2->core_temp, s3->exhaust_temp, s4->pressure, s7->fuel_flow,
        s11->vibration, s12->fan_speed, s15->core_speed)
     - the vibration rescale (raw s11 -> 0.2-1.4, using the frozen
       VIB_RAW_MIN/VIB_RAW_MAX constants baked into ml/sensor_map.py --
       NOT recomputed here, to avoid train/serve skew)
   This script does not reimplement any of that mapping/rescaling itself.

4. Assigns the 6 selected engines synthetic unit ids/offsets, in order of
   ascending target lifespan:

       target lifespan | unit_id | start offset (ticks)
       ----------------|---------|----------------------
       128             | M-011   | 10
       156             | M-014   | 40
       189             | M-017   | 95
       206             | M-021   | 5
       231             | M-023   | 130
       287             | M-029   | 0

   `unit_id` in the output CSV is the synthetic code (e.g. "M-011").
   `unit_name` is the original FD001 engine number (e.g. 39).

5. Builds a long-format table where every selected unit emits exactly one
   row at every global tick, from tick 0 to the max tick needed by any
   unit:
     - Before a unit's start offset, it HOLDS at its first row (cycle 1).
       So the unit "exists" and reports its cycle-1 reading from tick 0,
       but doesn't start actually progressing through cycles until its
       offset tick.
     - From the offset tick onward, the unit advances one cycle per tick.
     - Once a unit's own data is exhausted, it holds at its LAST row
       (its final recorded cycle) for all remaining ticks.

6. Writes data/scenarios/default.csv with columns:
     tick, unit_id, unit_name, cycle, <CONTRACT_KEYS in ml/sensor_map order>
   i.e.:
     tick, unit_id, unit_name, cycle, core_temp, exhaust_temp, fan_speed,
     core_speed, pressure, vibration, fuel_flow

USAGE
-----
    python sim/build_scenario.py
    (run from the repo root, so the relative data/ paths resolve; also
    works run directly since it adds the repo root to sys.path itself)
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Make the repo root importable (so `from ml.sensor_map import ...` works
# whether this script is run as `python sim/build_scenario.py` from the repo
# root, or imported some other way).
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ml.sensor_map import CONTRACT_KEYS, to_contract  # noqa: E402  (single source of truth)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

RAW_PATH = REPO_ROOT / "data" / "CMaps" / "train_FD001.txt"
OUT_PATH = REPO_ROOT / "data" / "scenarios" / "default.csv"

TARGET_LIFESPANS = [128, 156, 189, 206, 231, 287]
UNIT_IDS = ["M-011", "M-014", "M-017", "M-021", "M-023", "M-029"]
START_OFFSETS = [10, 40, 95, 5, 130, 0]

OUTPUT_COLUMNS = ["tick", "unit_id", "unit_name", "cycle"] + list(CONTRACT_KEYS)


# ---------------------------------------------------------------------------
# Load raw data
# ---------------------------------------------------------------------------

def load_raw(path: Path) -> pd.DataFrame:
    """Load train_FD001.txt into a DataFrame with named columns."""
    op_cols = [f"op{i}" for i in range(1, 4)]
    sensor_cols = [f"s{i}" for i in range(1, 22)]
    columns = ["unit", "cycle"] + op_cols + sensor_cols

    df = pd.read_csv(
        path,
        sep=r"\s+",
        header=None,
        names=columns,
        engine="python",
    )
    return df


# ---------------------------------------------------------------------------
# Engine selection
# ---------------------------------------------------------------------------

def select_engines(df: pd.DataFrame, targets: list[int]) -> list[int]:
    """
    For each target lifespan, pick the unit whose max cycle count is
    closest (by absolute difference). Each unit can only be used once;
    if two targets would pick the same unit, the next-closest unit is
    used for the later target.
    """
    lifespans = df.groupby("unit")["cycle"].max()

    chosen: list[int] = []
    used: set[int] = set()

    for target in targets:
        diffs = (lifespans - target).abs().sort_values()
        for unit, _ in diffs.items():
            if unit not in used:
                chosen.append(int(unit))
                used.add(int(unit))
                break

    return chosen


# ---------------------------------------------------------------------------
# Per-unit series prep
# ---------------------------------------------------------------------------

def build_unit_series(df: pd.DataFrame, unit: int) -> pd.DataFrame:
    """Extract one engine's rows, sorted by cycle, converted to the
    telemetry contract via ml.sensor_map.to_contract(). Returns a
    DataFrame indexed 0..N-1 in cycle order (index 0 == cycle 1), with
    columns ["cycle"] + CONTRACT_KEYS."""
    sub = df[df["unit"] == unit].sort_values("cycle").reset_index(drop=True)

    contract_rows = [to_contract(row) for _, row in sub.iterrows()]
    contract_df = pd.DataFrame(contract_rows, columns=CONTRACT_KEYS)
    contract_df.insert(0, "cycle", sub["cycle"].astype(int).values)
    return contract_df


# ---------------------------------------------------------------------------
# Long-format assembly
# ---------------------------------------------------------------------------

def assemble_long_format(
    unit_series: dict[str, pd.DataFrame],
    unit_names: dict[str, int],
    offsets: dict[str, int],
) -> list[dict]:
    """
    Build the long-format rows: every unit emits one row at every global
    tick from 0 to the max tick needed.

    Before its offset: hold at first row (cycle 1).
    From offset onward: advance one row (cycle) per tick.
    After its data runs out: hold at last row (final cycle).
    """
    max_tick = 0
    for unit_id, series in unit_series.items():
        offset = offsets[unit_id]
        last_tick_for_unit = offset + (len(series) - 1)
        max_tick = max(max_tick, last_tick_for_unit)

    rows: list[dict] = []
    for tick in range(max_tick + 1):
        for unit_id, series in unit_series.items():
            offset = offsets[unit_id]
            local_idx = tick - offset
            if local_idx < 0:
                local_idx = 0
            elif local_idx > len(series) - 1:
                local_idx = len(series) - 1

            row_data = series.iloc[local_idx]
            row = {
                "tick": tick,
                "unit_id": unit_id,
                "unit_name": unit_names[unit_id],
                "cycle": int(row_data["cycle"]),
            }
            for col in CONTRACT_KEYS:
                row[col] = row_data[col]
            rows.append(row)

    return rows


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if not RAW_PATH.exists():
        raise FileNotFoundError(
            f"Could not find {RAW_PATH}. Place train_FD001.txt at "
            f"data/CMaps/train_FD001.txt (relative to the repo root) and "
            f"re-run this script."
        )

    df = load_raw(RAW_PATH)

    chosen_units = select_engines(df, TARGET_LIFESPANS)
    print("Selected engines (by target lifespan):")
    lifespans = df.groupby("unit")["cycle"].max()
    for target, unit, unit_id, offset in zip(
        TARGET_LIFESPANS, chosen_units, UNIT_IDS, START_OFFSETS
    ):
        print(
            f"  target={target:>4} -> unit={unit:>3} "
            f"(actual lifespan={int(lifespans[unit])}) "
            f"-> unit_id={unit_id} offset={offset}"
        )

    unit_series = {}
    unit_names = {}
    offsets = {}
    for unit, unit_id, offset in zip(chosen_units, UNIT_IDS, START_OFFSETS):
        unit_series[unit_id] = build_unit_series(df, unit)
        unit_names[unit_id] = unit
        offsets[unit_id] = offset

    rows = assemble_long_format(unit_series, unit_names, offsets)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    print(f"\nWrote {len(rows)} rows to {OUT_PATH}")


if __name__ == "__main__":
    main()
