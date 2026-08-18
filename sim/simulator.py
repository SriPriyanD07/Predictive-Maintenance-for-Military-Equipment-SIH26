"""
simulator.py

Simulator: replays a scenario CSV (produced by build_scenario.py)
tick-by-tick.

Exposes TELEMETRY_KEYS, sourced directly from ml.sensor_map.CONTRACT_KEYS
(the project's frozen 7-key telemetry contract), so this module never
duplicates that list -- backend/main.py imports it from here:
    from sim.simulator import Simulator, TELEMETRY_KEYS

The scenario CSV is guaranteed (by build_scenario.py) to have exactly one
row per unit at every global tick, so each call to tick() advances by
exactly one tick and returns one dict per unit.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ml.sensor_map import CONTRACT_KEYS  # noqa: E402  (single source of truth)

# Re-exported for `from sim.simulator import Simulator, TELEMETRY_KEYS`.
TELEMETRY_KEYS = list(CONTRACT_KEYS)

DEFAULT_SCENARIO_NAME = "default"
SCENARIOS_DIR = REPO_ROOT / "data" / "scenarios"

# Columns that should be treated as numbers rather than strings when
# loading the CSV.
INT_COLS = {"tick", "cycle"}
FLOAT_COLS = set(TELEMETRY_KEYS)


class Simulator:
    """
    Replays a scenario CSV one global tick at a time.

    Usage:
        sim = Simulator(scenario="default")   # loads data/scenarios/default.csv
        sim.reset()
        readings = sim.tick()      # -> list[dict], one dict per unit
        sim.jump(50)               # jump straight to tick 50
        print(sim.tick_index)      # -> 50
    """

    def __init__(
        self,
        scenario: str = DEFAULT_SCENARIO_NAME,
        csv_path: str | Path | None = None,
    ):
        if csv_path is not None:
            self.csv_path = Path(csv_path)
        else:
            self.csv_path = SCENARIOS_DIR / f"{scenario}.csv"

        self._by_tick: dict[int, list[dict]] = {}
        self._load()
        self.reset()

    # -- loading -----------------------------------------------------

    def _load(self) -> None:
        """Load the CSV once into memory, grouped by tick."""
        if not self.csv_path.exists():
            raise FileNotFoundError(
                f"Scenario file not found: {self.csv_path}. "
                f"Run sim/build_scenario.py first to generate it."
            )

        by_tick: dict[int, list[dict]] = {}
        with self.csv_path.open(newline="") as f:
            reader = csv.DictReader(f)
            for raw_row in reader:
                row = self._coerce_row(raw_row)
                by_tick.setdefault(row["tick"], []).append(row)

        if not by_tick:
            raise ValueError(f"Scenario file {self.csv_path} has no rows.")

        self._by_tick = by_tick
        self._min_tick = min(by_tick.keys())
        self._max_tick = max(by_tick.keys())

    @staticmethod
    def _coerce_row(raw_row: dict) -> dict:
        row = dict(raw_row)
        for col in INT_COLS:
            row[col] = int(row[col])
        for col in FLOAT_COLS:
            row[col] = float(row[col])
        # unit_id stays a string (e.g. "M-011"). unit_name loads as a
        # string from CSV; cast to int if it's purely numeric, to match
        # build_scenario.py's output (original FD001 engine number).
        if "unit_name" in row:
            try:
                row["unit_name"] = int(row["unit_name"])
            except (TypeError, ValueError):
                pass
        return row

    # -- state ---------------------------------------------------------

    def reset(self) -> None:
        """Reset playback to just before the first tick. The next call
        to tick() will return the first tick's readings."""
        self._tick_index = self._min_tick - 1

    @property
    def tick_index(self) -> int:
        """The tick that was last emitted by tick()/jump(). Equal to
        (min_tick - 1) if reset() was just called and tick() hasn't been
        called yet."""
        return self._tick_index

    # -- playback --------------------------------------------------------

    def tick(self) -> list[dict]:
        """
        Advance one tick and return that tick's readings, one dict per
        unit. Once the last tick in the scenario has been reached,
        further calls keep returning the last tick's readings (the
        scenario doesn't loop or raise).
        """
        next_index = self._tick_index + 1
        if next_index > self._max_tick:
            next_index = self._max_tick
        self._tick_index = next_index
        return self._rows_at(self._tick_index)

    def jump(self, tick: int) -> list[dict]:
        """
        Jump directly to a given global tick and return that tick's
        readings. `tick` is clamped to the scenario's [min_tick, max_tick]
        range.
        """
        clamped = max(self._min_tick, min(tick, self._max_tick))
        self._tick_index = clamped
        return self._rows_at(self._tick_index)

    def _rows_at(self, tick: int) -> list[dict]:
        # Return copies so callers mutating the dicts can't corrupt the
        # in-memory scenario.
        return [dict(row) for row in self._by_tick[tick]]


if __name__ == "__main__":
    sim = Simulator(scenario="default")
    print(f"TELEMETRY_KEYS = {TELEMETRY_KEYS}")
    print(f"Loaded ticks {sim._min_tick}..{sim._max_tick}")
    sim.reset()
    first = sim.tick()
    print(f"tick_index={sim.tick_index}, {len(first)} units, e.g. {first[0]}")
    jumped = sim.jump(100)
    print(f"After jump(100): tick_index={sim.tick_index}, {len(jumped)} units")
