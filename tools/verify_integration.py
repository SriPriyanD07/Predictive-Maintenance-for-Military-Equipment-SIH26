"""M6 integration gate. Run before any demo.

    python tools/verify_integration.py            (offline checks only)
    python tools/verify_integration.py --api      (also hit a running backend)

Every check prints PASS or FAIL with the evidence, and the exit code is the
number of failures, so this is usable in CI or a pre-demo checklist.
"""

import json
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

API = "http://127.0.0.1:8000"

FAILURES = []


def check(name, ok, detail=""):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    if detail:
        for line in str(detail).strip().splitlines():
            print(f"       {line}")
    if not ok:
        FAILURES.append(name)
    return ok


def section(title):
    print()
    print(f"--- {title} " + "-" * max(0, 58 - len(title)))


# ---------------------------------------------------------------- modules ---
section("all five modules import together")

try:
    from ml.model import predict_rul, load_model, BASELINE
    from ml.sensor_map import CONTRACT_KEYS
    check("ml imports", True, f"{len(CONTRACT_KEYS)} contract keys")
except Exception as e:
    check("ml imports", False, e)

try:
    from decision.engine import decide
    check("decision imports", True)
except Exception as e:
    check("decision imports", False, e)

try:
    from sim.simulator import Simulator, TELEMETRY_KEYS
    check("sim imports", True)
except Exception as e:
    check("sim imports", False, e)

try:
    from backend.fallbacks import fallback_predict_rul, FallbackSimulator
    check("backend.fallbacks imports", True)
except Exception as e:
    check("backend.fallbacks imports", False, e)


# ------------------------------------------------------------- contracts ---
section("contract agreement between modules")

try:
    check(
        "TELEMETRY_KEYS == CONTRACT_KEYS",
        list(TELEMETRY_KEYS) == list(CONTRACT_KEYS),
        f"sim={list(TELEMETRY_KEYS)}",
    )
except Exception as e:
    check("TELEMETRY_KEYS == CONTRACT_KEYS", False, e)

# One BASELINE, not three. This was a real bug: fallbacks.py used to carry its
# own invented values and the fallback heuristic flatlined as a result.
try:
    from ml.sensor_map import BASELINE as SM_BASELINE
    from backend.fallbacks import BASELINE as FB_BASELINE
    check(
        "single BASELINE shared by ml + backend",
        SM_BASELINE is FB_BASELINE,
        f"core_speed={FB_BASELINE['core_speed']} (an invented 9000 would mean skew)",
    )
except Exception as e:
    check("single BASELINE shared by ml + backend", False, e)

# The simulator must expose .units or backend/main.py raises on startup.
try:
    scen = ROOT / "data" / "scenarios" / "default.csv"
    if not scen.exists():
        check("Simulator.units exists", False, "scenario CSV missing; run sim/build_scenario.py")
    else:
        s = Simulator(scenario="default")
        u = s.units
        ok = isinstance(u, list) and len(u) > 0 and "unit_id" in u[0] and "unit_name" in u[0]
        check("Simulator.units exists (backend startup needs it)", ok, f"{len(u)} units, first={u[0]}")
        names_ok = all(not str(x["unit_name"]).isdigit() for x in u)
        check(
            "unit_name is a display string, not the raw engine number",
            names_ok,
            f"first name={u[0]['unit_name']!r}",
        )
except Exception as e:
    check("Simulator.units exists (backend startup needs it)", False, e)


# ---------------------------------------------------------------- skew -----
section("train/serve skew (the silent demo killer)")

try:
    r = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "check_skew.py")],
        capture_output=True, text=True, cwd=str(ROOT), timeout=600,
    )
    tail = [l for l in r.stdout.splitlines() if "RESULT" in l or "SKEW" in l]
    check("all channels within training range", r.returncode == 0, "\n".join(tail) or r.stdout[-300:])
except Exception as e:
    check("all channels within training range", False, e)


# -------------------------------------------------------------- pipeline ---
section("end-to-end sim -> ml -> decision")

try:
    load_model()
    sim = Simulator(scenario="default")
    hist = {}
    levels = set()
    for t in range(200):
        for row in sim.tick():
            uid = row["unit_id"]
            w = hist.setdefault(uid, [])
            w.append({**{k: row[k] for k in CONTRACT_KEYS}, "cycle": row["cycle"]})
            if len(w) > 30:
                w.pop(0)
    for uid, w in hist.items():
        rul, lo, hi = predict_rul(w)
        d = decide(rul, w, [])
        levels.add(d["risk_level"])
    check(
        "pipeline produces a spread of risk levels (not one constant)",
        len(levels) >= 2,
        f"levels seen at tick 200: {sorted(levels)}",
    )
except Exception as e:
    check("pipeline produces a spread of risk levels (not one constant)", False, e)


# ---------------------------------------------------------------- tests ----
section("M2 decision test suite")

try:
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "decision", "-q"],
        capture_output=True, text=True, cwd=str(ROOT), timeout=600,
    )
    last = [l for l in r.stdout.splitlines() if "passed" in l or "failed" in l]
    check("pytest decision", r.returncode == 0, "\n".join(last[-2:]))
except Exception as e:
    check("pytest decision", False, e)


# --------------------------------------------------------------- frontend --
section("frontend")

pkg = ROOT / "frontend" / "package.json"
nm = ROOT / "frontend" / "node_modules"
check("frontend/node_modules installed", nm.exists(), "" if nm.exists() else "run npm install in frontend/")

vite_cfg = (ROOT / "frontend" / "vite.config.ts").read_text() if (ROOT / "frontend" / "vite.config.ts").exists() else ""
check("vite proxies /api to the backend", "'/api'" in vite_cfg and "proxy" in vite_cfg,
      "without this the browser cannot reach the model")

api_ts = ROOT / "frontend" / "src" / "data" / "api.ts"
check("frontend has an API adapter", api_ts.exists(),
      "" if api_ts.exists() else "frontend would render mock data only")

# The bug that broke `npm run build` for the whole team.
vt = (ROOT / "frontend" / "src" / "components" / "dashboard" / "VehicleTable.tsx")
if vt.exists():
    check("no unused RISK_ORDER (breaks tsc -b)", "RISK_ORDER" not in vt.read_text())


# ------------------------------------------------------------------- api ---
if "--api" in sys.argv:
    section("live API")

    def get(path):
        with urllib.request.urlopen(API + path, timeout=10) as r:
            return json.load(r)

    def post(path, body=None):
        data = json.dumps(body).encode() if body else b""
        req = urllib.request.Request(
            API + path, data=data, method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.load(r)

    try:
        h = get("/api/health")
        mods = h.get("modules", {})
        check(
            "GET /api/health - all modules live",
            all(mods.get(k) for k in ("ml", "decision", "sim")) and h.get("model_loaded"),
            f"modules={mods} model_loaded={h.get('model_loaded')} source={h.get('source')}",
        )
    except Exception as e:
        check("GET /api/health", False, f"{e}  (is the backend running? .\\run_all.ps1)")

    try:
        m = get("/api/metrics")
        want = {"model", "dataset", "mae", "rmse", "n_test",
                "baseline_mae", "lead_time_cycles", "trained_at"}
        check("GET /api/metrics - exactly the 8 agreed keys", set(m) == want,
              f"mae={m.get('mae')} lead_time={m.get('lead_time_cycles')}")
    except Exception as e:
        check("GET /api/metrics", False, e)

    try:
        post("/api/sim/reset")
        post("/api/sim/start")
        post("/api/sim/jump", {"tick": 40})
        early = {u["unit_id"]: u["rul"] for u in get("/api/fleet")["units"]}
        post("/api/sim/jump", {"tick": 200})
        late = {u["unit_id"]: u["rul"] for u in get("/api/fleet")["units"]}
        dropped = [k for k in early if late.get(k, 0) < early[k] - 5]
        check(
            "RUL actually falls as units degrade (not a constant)",
            len(dropped) >= 1,
            "tick 40 -> 200: " + ", ".join(f"{k} {early[k]:.0f}->{late[k]:.0f}" for k in sorted(early)),
        )
    except Exception as e:
        check("RUL falls as units degrade", False, e)

    try:
        f = get("/api/fleet")
        u = f["units"][0]
        need = ["unit_id", "unit_name", "rul", "rul_band", "risk_level", "risk_score",
                "priority", "action_code", "recommended_action", "reason",
                "health_index", "telemetry"]
        missing = [k for k in need if k not in u]
        check("GET /api/fleet - every field the UI needs", not missing,
              f"missing={missing}" if missing else f"{len(f['units'])} units, all fields present")
        check("unit_name is a display string in the API too", not str(u["unit_name"]).isdigit(),
              f"unit_name={u['unit_name']!r}")
    except Exception as e:
        check("GET /api/fleet", False, e)


# ----------------------------------------------------------------- result --
print()
print("=" * 64)
if FAILURES:
    print(f"RESULT: {len(FAILURES)} FAILED -> {', '.join(FAILURES)}")
else:
    print("RESULT: all checks passed. Integration is demo-ready.")
print("=" * 64)
sys.exit(len(FAILURES))
