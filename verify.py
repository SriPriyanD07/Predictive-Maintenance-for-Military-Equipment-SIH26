import json
import os
import subprocess
import sys
import time

import requests

BASE = "http://127.0.0.1:8000"
FAILED = False

REQUIRED_UNIT_KEYS = {
    "unit_id", "unit_name", "tick", "cycle", "timestamp", "telemetry",
    "rul", "rul_band", "health_index", "risk_score", "risk_level",
    "priority", "action_code", "recommended_action", "reason", "source",
}
TELEMETRY_KEYS = {
    "core_temp", "exhaust_temp", "fan_speed", "core_speed",
    "pressure", "vibration", "fuel_flow",
}
RISK_LEVELS = {"NOMINAL", "WATCH", "WARNING", "CRITICAL"}
PRIORITIES = {"P4", "P3", "P2", "P1"}
ACTION_CODES = {"MONITOR", "INSPECT_7D", "SCHEDULE_72H", "SERVICE_24H", "GROUND_NOW"}


def check(name, cond, detail=""):
    global FAILED
    if cond:
        print(f"PASS {name}")
    else:
        FAILED = True
        print(f"FAIL {name} {detail}")


def wait_for_server(timeout=15):
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get(f"{BASE}/api/health", timeout=1)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.3)
    return False


def validate_unit(u):
    if not REQUIRED_UNIT_KEYS.issubset(u.keys()):
        return False, f"missing keys {REQUIRED_UNIT_KEYS - u.keys()}"
    if set(u["telemetry"].keys()) != TELEMETRY_KEYS:
        return False, "bad telemetry keys"
    if any(v is None for v in u["telemetry"].values()):
        return False, "null telemetry value"
    if not (0 <= u["rul"] <= 125):
        return False, "rul out of range"
    if not (0 <= u["health_index"] <= 1):
        return False, "health_index out of range"
    if not (0 <= u["risk_score"] <= 1):
        return False, "risk_score out of range"
    if u["risk_level"] not in RISK_LEVELS:
        return False, "bad risk_level"
    if u["priority"] not in PRIORITIES:
        return False, "bad priority"
    if u["action_code"] not in ACTION_CODES:
        return False, "bad action_code"
    if u["source"] not in ("model", "cached"):
        return False, "bad source"
    if len(u["recommended_action"]) > 60:
        return False, "recommended_action too long"
    if len(u["reason"]) > 120:
        return False, "reason too long"
    if not u["timestamp"].endswith("Z"):
        return False, "timestamp missing Z"
    return True, ""


def run_export_demo():
    r = subprocess.run(
        [sys.executable, "-m", "backend.export_demo"],
        capture_output=True, text=True,
    )
    check("export_demo.py runs cleanly", r.returncode == 0, r.stderr[-500:])
    out_path = "mock/scenario_fixed.json"
    check("scenario_fixed.json created", os.path.exists(out_path))
    if os.path.exists(out_path):
        with open(out_path) as f:
            data = json.load(f)
        check("scenario_fixed.json has 200 ticks", len(data.get("ticks", [])) == 200)


def run_cached_mode():
    env = os.environ.copy()
    env["USE_CACHED"] = "1"
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8002"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env,
    )
    try:
        base = "http://127.0.0.1:8002"
        start = time.time()
        up = False
        while time.time() - start < 15:
            try:
                if requests.get(f"{base}/api/health", timeout=1).status_code == 200:
                    up = True
                    break
            except Exception:
                pass
            time.sleep(0.3)
        check("USE_CACHED server startup", up)
        if not up:
            return

        r = requests.get(f"{base}/api/health")
        h = r.json()
        check("USE_CACHED health source == cached", h.get("source") == "cached")

        requests.post(f"{base}/api/sim/start")
        time.sleep(1.5)
        requests.post(f"{base}/api/sim/pause")

        r = requests.get(f"{base}/api/fleet")
        fleet = r.json()
        check("USE_CACHED fleet status", r.status_code == 200)
        units = fleet.get("units", [])
        check("USE_CACHED fleet has 6 units", len(units) == 6)
        check(
            "USE_CACHED fleet source == cached for all units",
            len(units) > 0 and all(u["source"] == "cached" for u in units),
        )
        if units:
            ok, detail = validate_unit(units[0])
            check("USE_CACHED unit shape identical to live shape", ok, detail)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


def main():
    run_export_demo()
    run_cached_mode()

    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8000"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        if not wait_for_server():
            check("server startup", False, "server did not become healthy")
            return

        r = requests.get(f"{BASE}/api/health")
        check("GET /api/health status", r.status_code == 200)
        h = r.json()
        check("health has units==6", h.get("units") == 6, h)
        modules = h.get("modules", {})
        sim_dir_present = os.path.isdir("sim")
        ml_dir_present = os.path.isdir("ml")
        decision_dir_present = os.path.isdir("decision")
        check("health modules.sim matches directory presence", modules.get("sim") == sim_dir_present, modules)
        check("health modules.ml matches directory presence", modules.get("ml") == ml_dir_present, modules)
        check("health modules.decision matches directory presence", modules.get("decision") == decision_dir_present, modules)

        r = requests.get(f"{BASE}/api/fleet")
        check("GET /api/fleet status", r.status_code == 200)
        fleet = r.json()
        check("fleet has 6 units", len(fleet.get("units", [])) == 6)
        ok, detail = validate_unit(fleet["units"][0])
        check("unit shape valid", ok, detail)
        check("live mode source == model", all(u["source"] == "model" for u in fleet["units"]))

        expected_ids = {"M-011", "M-014", "M-017", "M-021", "M-023", "M-029"}
        actual_ids = {u["unit_id"] for u in fleet["units"]}
        check("fleet unit_ids match required set", actual_ids == expected_ids, actual_ids)
        check("M-017 hero unit present", "M-017" in actual_ids)

        r = requests.post(f"{BASE}/api/sim/start")
        check("POST /api/sim/start", r.status_code == 200 and r.json().get("running") is True)

        time.sleep(2.2)
        r2 = requests.get(f"{BASE}/api/fleet")
        check("tick advances while running", r2.json()["tick"] > fleet["tick"])

        r = requests.post(f"{BASE}/api/sim/pause")
        check("POST /api/sim/pause", r.status_code == 200 and r.json().get("running") is False)

        unit_id = fleet["units"][0]["unit_id"]
        r = requests.get(f"{BASE}/api/unit/{unit_id}/history?window=50")
        check("unit history status", r.status_code == 200)
        check("unit history has points", len(r.json().get("points", [])) > 0)

        r = requests.get(f"{BASE}/api/unit/UNKNOWN/history")
        check("unknown unit history 404", r.status_code == 404)

        r = requests.get(f"{BASE}/api/metrics")
        check("GET /api/metrics status", r.status_code == 200)
        m = r.json()
        check("metrics has model field", "model" in m and "dataset" in m)

        r = requests.post(f"{BASE}/api/sim/speed", json={"speed": 4})
        check("valid speed accepted", r.status_code == 200 and r.json().get("speed") == 4)

        r = requests.post(f"{BASE}/api/sim/speed", json={"speed": 7})
        check("invalid speed rejected", r.status_code == 422)

        cur_tick = requests.get(f"{BASE}/api/health").json()["tick"]
        target = cur_tick + 30
        r = requests.post(f"{BASE}/api/sim/jump", json={"tick": target})
        check("jump reaches target tick", r.status_code == 200 and r.json().get("tick") == target)

        r = requests.get(f"{BASE}/api/unit/{unit_id}/history?window=200")
        check("history populated after jump", len(r.json()["points"]) > 1)

        r = requests.post(f"{BASE}/api/sim/reset")
        check("POST /api/sim/reset", r.status_code == 200 and r.json() == {"tick": 0, "running": False})

        r = requests.get(f"{BASE}/api/unit/{unit_id}/history")
        check("history cleared after reset", len(r.json()["points"]) == 0)

        r = requests.options(
            f"{BASE}/api/fleet",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        check("CORS preflight GET /api/fleet status 200", r.status_code == 200, r.status_code)
        check(
            "CORS preflight GET /api/fleet allow-origin",
            r.headers.get("access-control-allow-origin") == "http://localhost:5173",
            r.headers.get("access-control-allow-origin"),
        )

        r = requests.options(
            f"{BASE}/api/sim/start",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        check("CORS preflight POST /api/sim/start status 200", r.status_code == 200, r.status_code)
        check(
            "CORS preflight POST /api/sim/start allow-origin",
            r.headers.get("access-control-allow-origin") == "http://localhost:5173",
            r.headers.get("access-control-allow-origin"),
        )

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()

    if FAILED:
        sys.exit(1)


if __name__ == "__main__":
    main()
