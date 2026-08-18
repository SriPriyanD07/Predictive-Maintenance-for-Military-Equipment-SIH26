# Integration notes (M6)

This branch merges all five module branches and fixes what broke when they met.

    origin/main         backend/ + frontend/
    origin/m1-ml        ml/ + tools/
    origin/m2-decision  decision/
    origin/telemetry    sim/

## Run it

```powershell
.\run_all.ps1                    # backend :8000, frontend :5173
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/sim/start
.\run_all.ps1 -Stop
```

Then open <http://127.0.0.1:5173>.

Verify before demoing:

```powershell
python tools\verify_integration.py --api
```

Exit code is the number of failures, so it works as a CI gate.

`data/` is gitignored. You need `data/CMaps/train_FD001.txt` locally; the
scenario CSV is generated from it by `sim/build_scenario.py` (run_all does this
automatically). You do **not** need the data to run the model — `ml/model.pkl`
is committed.

## Ports are coupled

`backend/main.py` CORS-allows only 5173, and `frontend/vite.config.ts` proxies
`/api` to 8000. Change one, change the other. The proxy is why no CORS edit was
needed: the browser only ever talks to the Vite origin.

## What was broken at the merge, and why

**1. Backend would not boot.** `backend/main.py:71` reads `state.sim.units`;
`sim.simulator.Simulator` never exposed it, so startup died with
`AttributeError`. Added a `units` property — the data was already in the
scenario, just unexposed.

**2. Vehicles displayed as "39".** `sim/build_scenario.py` documents
`unit_name` as the source FD001 engine number (an int), but
`backend/fallbacks.py` emits it as a display string and the frontend renders it
verbatim. Now `_coerce_row` keeps the number as `source_engine` and sets
`unit_name` to `"Turbofan Engine 011"`.

**3. `npm run build` failed for everyone.** `VehicleTable.tsx` declared
`RISK_ORDER` and never used it; `tsc -b` fails on TS6133. Removed.

**4. `fallbacks.py` had invented telemetry constants.** `BASELINE`,
`_SPREAD` and `_DECREASING` were hand-written "realistic-looking" engine
numbers (`core_speed: 9000`, `pressure: 14.5`) chosen before the C-MAPSS
contract existed. Five of seven sat outside the model's training range and the
degradation direction was backwards on three channels — `core_speed` and
`pressure` rise as a unit degrades, `fuel_flow` falls.

Measured effect on real unit 1: the fallback heuristic returned a flat
**28–33 RUL across a 192-cycle life** (spread 4.72) and rated a brand-new
engine as critical. After the fix: 121 → 75, spread 46.45.

All three now live only in `ml/sensor_map.py`, which has **no third-party
imports** on purpose — `backend/fallbacks.py` must keep working on a machine
where the ML stack was never installed, which is the whole reason it exists.
Verified with numpy, xgboost, sklearn, pandas, joblib and matplotlib all
blocked.

**5. The frontend never called the backend.** No branch had any wiring — every
page ran off `src/data/mockFleet.ts`. Added `src/data/api.ts` (adapter),
`src/hooks/useFleet.tsx` (single poll, 2s), and pointed all seven pages at it.

## Honesty about what is real on screen

`LiveBadge` in the header shows LIVE or MOCK. If the backend dies the UI falls
back to fixtures rather than blanking, so **without that badge a dead backend
looks identical to a working one.** Do not remove it before a demo.

Per field, from `src/data/api.ts`:

| real (model / decision output) | derived | synthetic |
|---|---|---|
| RUL, risk level, risk score, health index, priority, action code, recommended action, reason, telemetry, history, MAE, RMSE, lead time | `likelyFailingPart` (largest telemetry drift vs BASELINE), `rulDays` (1 cycle = 1 day), `rulAccuracyPct` (from MAE) | `fleetGroup`, `inspectionChecklist` |

Still **entirely mock**, because the backend has no such data:

- **Spare Parts page** — every number is fiction. If a judge asks about a
  shortage, say so.
- Analytics tiles **F1 fault detection**, **downtime reduction**, **spare parts
  forecast error** — all render 0; they were never measured.
- `rulHistory.actualRul` is `null` by design: the true RUL of a live unit is
  unknowable at serve time, so the chart draws prediction plus confidence band
  only. Do not fabricate an "actual" line.

## Model

Trained on real NASA C-MAPSS FD001: 100 engines, 20,631 rows, 80/20 split by
engine (seed 42), 30-cycle sliding windows, 16,390 x 50 feature matrix,
XGBRegressor with 300 trees.

| metric | value |
|---|---|
| MAE | 13.43 cycles |
| RMSE | 18.30 |
| baseline (predict mean) MAE | 34.83 |
| median lead time | 42 cycles |
| scored on | 100 official test engines vs `RUL_FD001.txt` |

No retrain was needed after `141e515`: its only `ml/` change is an additive
`DELTA` dict — `rescale_vibration`, `BASELINE`, `SPREAD` and `features.py` are
untouched, so the committed pickle still matches the feature pipeline.

**Dataset provenance caveat:** the C-MAPSS files came from the Hugging Face
mirror `DeveloperMindset123/CMAPSS_Jet_Engine_Simulated_Data`, not NASA
directly (Kaggle needs an account). Structure and format were verified — 26
space-separated columns, no header, and NASA's own `readme.txt` and
`Damage Propagation Modeling.pdf` ship alongside. But **no published checksum
exists on either side**, so bit-identity with NASA's archive is unproven. Worth
a cross-check against the Kaggle mirror if anyone has an account.

## Not done

- **Nothing here is pushed.** This is a local `integration` branch only.
- `git merge` into `main` will hit the same `backend/fallbacks.py` conflict
  seen here. Resolution: take M1's version (it carries the constants fix plus
  the simulator-scale and vibration-normalisation work), then drop
  `_with_model` per M3's `d6b815d`. Do **not** take `main`'s side wholesale —
  it reintroduces the flatline bug.
- Spare parts needs a real backend endpoint, or the page should be labelled
  illustrative in the pitch.
