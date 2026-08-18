import json
from datetime import datetime, timezone
from pathlib import Path

try:
    from ml.model import predict_rul, load_model
except Exception:
    from backend.fallbacks import fallback_predict_rul as predict_rul

    def load_model(path="ml/model.pkl"):
        return None

try:
    from decision.engine import decide
except Exception:
    from backend.fallbacks import fallback_decide as decide

try:
    from sim.simulator import Simulator, TELEMETRY_KEYS
except Exception:
    from backend.fallbacks import FallbackSimulator as Simulator, TELEMETRY_KEYS

TICKS = 200
WINDOW_CAP = 30
OUT_PATH = Path("mock/scenario_fixed.json")


def _now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run():
    load_model("ml/model.pkl")
    sim = Simulator(scenario="default")
    windows = {u["unit_id"]: [] for u in sim.units}
    histories = {u["unit_id"]: [] for u in sim.units}
    ticks_out = []

    for _ in range(TICKS):
        raw = sim.tick()
        tick_index = sim.tick_index
        units_out = []
        for t in raw:
            unit_id = t["unit_id"]
            unit_name = t["unit_name"]
            cycle = t["cycle"]
            telemetry = {k: float(t[k]) for k in TELEMETRY_KEYS}

            win = windows[unit_id]
            win.append({**telemetry, "cycle": cycle})
            if len(win) > WINDOW_CAP:
                del win[0]

            rul, low, high = predict_rul(win)
            rul = max(0.0, min(125.0, float(rul)))
            low = max(0.0, min(125.0, float(low)))
            high = max(0.0, min(125.0, float(high)))

            hist = histories[unit_id]
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
                "source": "cached",
            }
            hist.append({
                "tick": tick_index,
                "cycle": cycle,
                "rul": unit_state["rul"],
                "risk_score": unit_state["risk_score"],
                "risk_level": unit_state["risk_level"],
                "telemetry": telemetry,
            })
            units_out.append(unit_state)
        ticks_out.append({"tick": tick_index, "units": units_out})

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump({"ticks": ticks_out}, f)
    print(f"wrote {len(ticks_out)} ticks to {OUT_PATH}")


if __name__ == "__main__":
    run()
