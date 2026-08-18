import asyncio
import json
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

MODULES = {"ml": False, "decision": False, "sim": False}

try:
    from ml.model import predict_rul, load_model, BASELINE
    MODULES["ml"] = True
except Exception:
    from backend.fallbacks import fallback_predict_rul as predict_rul, BASELINE

    def load_model(path="ml/model.pkl"):
        return None

try:
    from decision.engine import decide
    MODULES["decision"] = True
except Exception:
    from backend.fallbacks import fallback_decide as decide

try:
    from sim.simulator import Simulator, TELEMETRY_KEYS
    MODULES["sim"] = True
except Exception:
    from backend.fallbacks import FallbackSimulator as Simulator, TELEMETRY_KEYS

HISTORY_CAP = 500
WINDOW_CAP = 30
ALLOWED_SPEEDS = (1, 4, 10)
USE_CACHED = os.environ.get("USE_CACHED") == "1"
CACHED_SCENARIO_PATH = Path("mock/scenario_fixed.json")


class SpeedBody(BaseModel):
    speed: int


class JumpBody(BaseModel):
    tick: int


class State:
    def __init__(self):
        self.sim = Simulator(scenario="default")
        self.running = False
        self.speed = 1
        self.fleet = []
        self.histories = {}
        self.windows = {}
        self.task = None
        self.cached_ticks = []
        self.model_loaded = False


state = State()


def _now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _init_buffers():
    state.histories = {u["unit_id"]: [] for u in state.sim.units}
    state.windows = {u["unit_id"]: [] for u in state.sim.units}
    fleet = []
    for u in state.sim.units:
        fleet.append({
            "unit_id": u["unit_id"],
            "unit_name": u["unit_name"],
            "tick": 0,
            "cycle": 0,
            "timestamp": _now_iso(),
            "telemetry": dict(BASELINE),
            "rul": 125.0,
            "rul_band": {"low": 110.0, "high": 125.0},
            "health_index": 1.0,
            "risk_score": 0.0,
            "risk_level": "NOMINAL",
            "priority": "P4",
            "action_code": "MONITOR",
            "recommended_action": "Continue normal operation, monitor telemetry",
            "reason": "Unit nominal at simulation start",
            "source": "cached" if USE_CACHED else "model",
        })
    state.fleet = fleet


def _step_cached():
    if not state.cached_ticks:
        return
    try:
        state.sim.tick()
    except Exception:
        return
    idx = min(state.sim.tick_index - 1, len(state.cached_ticks) - 1)
    entry = state.cached_ticks[idx]
    fleet = []
    for u in entry["units"]:
        unit_state = dict(u)
        unit_state["tick"] = state.sim.tick_index
        unit_state["timestamp"] = _now_iso()
        unit_state["source"] = "cached"
        fleet.append(unit_state)
        hist = state.histories.setdefault(unit_state["unit_id"], [])
        hist.append({
            "tick": unit_state["tick"],
            "cycle": unit_state["cycle"],
            "rul": unit_state["rul"],
            "risk_score": unit_state["risk_score"],
            "risk_level": unit_state["risk_level"],
            "telemetry": unit_state["telemetry"],
        })
        if len(hist) > HISTORY_CAP:
            del hist[0]
    if fleet:
        state.fleet = fleet


def step_once():
    if USE_CACHED:
        _step_cached()
        return
    try:
        ticks = state.sim.tick()
    except Exception:
        return
    tick_index = state.sim.tick_index
    fleet = []
    for t in ticks:
        try:
            unit_id = t["unit_id"]
            unit_name = t["unit_name"]
            cycle = t["cycle"]
            telemetry = {k: float(t[k]) for k in TELEMETRY_KEYS}

            win = state.windows.setdefault(unit_id, [])
            win.append({**telemetry, "cycle": cycle})
            if len(win) > WINDOW_CAP:
                del win[0]

            rul, low, high = predict_rul(win)
            rul = max(0.0, min(125.0, float(rul)))
            low = max(0.0, min(125.0, float(low)))
            high = max(0.0, min(125.0, float(high)))

            hist = state.histories.setdefault(unit_id, [])
            decision = decide(rul, win, hist)

            unit_state = {
                "unit_id": unit_id,
                "unit_name": unit_name,
                "tick": tick_index,
                "cycle": cycle,
                "timestamp": _now_iso(),
                "telemetry": telemetry,
                "rul": round(rul, 2),
                "rul_band": {"low": round(low, 2), "high": round(high, 2)},
                "health_index": decision.get("health_index", 0.0),
                "risk_score": decision.get("risk_score", 0.0),
                "risk_level": decision.get("risk_level", "NOMINAL"),
                "priority": decision.get("priority", "P4"),
                "action_code": decision.get("action_code", "MONITOR"),
                "recommended_action": decision.get("recommended_action", "Continue normal operation"),
                "reason": decision.get("reason", "No data"),
                "source": "model",
            }

            hist.append({
                "tick": tick_index,
                "cycle": cycle,
                "rul": unit_state["rul"],
                "risk_score": unit_state["risk_score"],
                "risk_level": unit_state["risk_level"],
                "telemetry": telemetry,
            })
            if len(hist) > HISTORY_CAP:
                del hist[0]

            fleet.append(unit_state)
        except Exception:
            continue
    if fleet:
        state.fleet = fleet


async def _tick_loop():
    while True:
        try:
            if state.running:
                step_once()
                interval = 1.0 / max(state.speed, 1)
            else:
                interval = 0.2
            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            raise
        except Exception:
            await asyncio.sleep(0.5)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if USE_CACHED:
        try:
            with open(CACHED_SCENARIO_PATH) as f:
                state.cached_ticks = json.load(f).get("ticks", [])
        except Exception:
            state.cached_ticks = []
    else:
        loaded = load_model("ml/model.pkl")
        state.model_loaded = loaded is not None
    _init_buffers()
    state.task = asyncio.create_task(_tick_loop())
    try:
        yield
    finally:
        if state.task:
            state.task.cancel()
            try:
                await state.task
            except asyncio.CancelledError:
                pass


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def get_health():
    return {
        "status": "ok",
        "source": "cached" if USE_CACHED else "model",
        "tick": state.sim.tick_index,
        "running": state.running,
        "model_loaded": state.model_loaded,
        "units": len(state.sim.units),
        "modules": MODULES,
    }


@app.get("/api/fleet")
def get_fleet():
    return {"tick": state.sim.tick_index, "running": state.running, "units": state.fleet}


@app.get("/api/unit/{unit_id}/history")
def get_unit_history(unit_id: str, window: int = 120):
    if unit_id not in state.histories:
        raise HTTPException(status_code=404, detail="unknown unit_id")
    w = max(1, min(window, 200))
    hist = state.histories[unit_id][-w:]
    points = [
        {
            "tick": h["tick"],
            "cycle": h["cycle"],
            "rul": h["rul"],
            "risk_score": h["risk_score"],
            "risk_level": h["risk_level"],
            "telemetry": h["telemetry"],
        }
        for h in hist
    ]
    return {"unit_id": unit_id, "points": points}


@app.get("/api/metrics")
def get_metrics():
    default = {
        "model": "XGBoost",
        "dataset": "NASA C-MAPSS FD001",
        "mae": None,
        "rmse": None,
        "n_test": None,
        "baseline_mae": None,
        "lead_time_cycles": None,
        "trained_at": None,
    }
    path = Path("ml/metrics.json")
    if path.exists():
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:
            return default
    return default


@app.post("/api/sim/start")
def sim_start():
    state.running = True
    return {"running": True}


@app.post("/api/sim/pause")
def sim_pause():
    state.running = False
    return {"running": False}


@app.post("/api/sim/reset")
def sim_reset():
    state.sim.reset()
    state.running = False
    _init_buffers()
    return {"tick": state.sim.tick_index, "running": False}


@app.post("/api/sim/speed")
def sim_speed(body: SpeedBody):
    if body.speed not in ALLOWED_SPEEDS:
        raise HTTPException(status_code=422, detail="speed must be 1, 4, or 10")
    state.speed = body.speed
    return {"speed": state.speed}


@app.post("/api/sim/jump")
def sim_jump(body: JumpBody):
    if body.tick < 0:
        raise HTTPException(status_code=422, detail="tick must be >= 0")
    while state.sim.tick_index < body.tick:
        step_once()
    return {"tick": state.sim.tick_index}
