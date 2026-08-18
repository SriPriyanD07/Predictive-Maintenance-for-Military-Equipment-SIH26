# Predictive Maintenance PoC — Backend

Single-process FastAPI backend simulating a fleet of 6 turbofan engines, predicting RUL
(remaining useful life), and issuing maintenance decisions.

## Setup

```bash
python -m venv .venv
source .venv/Scripts/activate   # Windows Git Bash; use .venv\Scripts\activate.bat on cmd
pip install -r requirements.txt
```

## Start the server

```bash
bash run_backend.sh
```

Equivalent to `uvicorn backend.main:app --reload --port 8000`.

Fleet state advances automatically on a timer once `POST /api/sim/start` is called — there is no
manual tick endpoint. Poll `GET /api/fleet` (the dashboard polls it every second).

## Run verification

```bash
bash verify.sh
```

Boots the server, exercises all 9 endpoints, checks the cached-replay path, CORS preflight, and
the demo-export script. Every line should print `PASS`.

## Endpoints

- `GET /api/health` → `{"status":"ok","source":"model","tick":128,"running":true,"model_loaded":false,"units":6,"modules":{"ml":false,"decision":false,"sim":false}}`
- `GET /api/fleet` → `{"tick":128,"running":true,"units":[UnitState, ...]}`
- `GET /api/unit/{unit_id}/history?window=120` → `{"unit_id":"M-017","points":[{"tick":8,"cycle":8,"rul":124.0,"risk_score":0.04,"risk_level":"NOMINAL","telemetry":{...}}]}` (404 if `unit_id` unknown; window capped at 200)
- `GET /api/metrics` → `{"model":"XGBoost","dataset":"NASA C-MAPSS FD001","mae":null,"rmse":null,"n_test":null,"baseline_mae":null,"lead_time_cycles":null,"trained_at":null}` (or contents of `ml/metrics.json` if present)
- `POST /api/sim/start` → `{"running":true}`
- `POST /api/sim/pause` → `{"running":false}`
- `POST /api/sim/reset` → `{"tick":0,"running":false}` (also clears all history buffers)
- `POST /api/sim/speed` body `{"speed":4}` → `{"speed":4}` (only 1, 4, 10 accepted)
- `POST /api/sim/jump` body `{"tick":150}` → `{"tick":150}` (runs ticks silently up to N, populating history)

## Cached / replay mode

Set `USE_CACHED=1` to skip live computation and replay a pre-generated fixture instead:

```bash
python -m backend.export_demo          # writes mock/scenario_fixed.json (200 ticks)
USE_CACHED=1 uvicorn backend.main:app --port 8000
```

In this mode every `UnitState.source` is `"cached"`, and the same endpoints serve fixture data
instead of running the simulator/model/decision pipeline.

## Ownership: this contribution is `backend/` only

`sim/`, `ml/`, and `decision/` are **not part of this contribution** — they belong to other
developers on the team. `backend/main.py` imports them if present (`from ml.model import
predict_rul`, etc.) and falls back to the equivalent logic in `backend/fallbacks.py`
(`FallbackSimulator`, `fallback_predict_rul`, `fallback_decide`) if they are absent. The server
boots and every check in `verify.sh` passes with those three directories deleted entirely —
`GET /api/health` reports which ones are real vs. fallback in its `modules` field.

Dropping a real trained model into `ml/model.pkl` is picked up automatically at startup by
`load_model()` — no code change required, and no restart-time configuration beyond the file
existing on disk.
