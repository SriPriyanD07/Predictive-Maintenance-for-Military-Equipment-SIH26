# M6: one-command startup for the whole stack.
#
#   .\run_all.ps1            start backend + frontend
#   .\run_all.ps1 -Stop      stop whatever is on the two ports
#
# Backend on 8000, frontend on 5173. Those two ports are not arbitrary:
# backend/main.py CORS-allows 5173, and frontend/vite.config.ts proxies /api to
# 8000. Change one and you must change the other.

param(
    [switch]$Stop,
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 5173,

    # A fresh backend starts paused at tick -1, so the dashboard would open on
    # an empty fleet. After startup we advance to a tick that actually shows a
    # spread of risk levels. Tick 160 is the only tick in the 361-tick scenario
    # where all four levels (NOMINAL/WATCH/WARNING/CRITICAL) appear at once.
    [int]$Tick = 160,

    # Default is RUNNING: the dashboard should visibly move, which is the point
    # of a live telemetry demo. Caveat: it advances ~1 tick/second and the
    # scenario ends at tick 361, so from tick 160 you get roughly 3 minutes
    # before every unit is CRITICAL and the screen is a wall of red. Re-run the
    # script to jump back to a good tick.
    #
    # -Pause holds the opening state indefinitely instead.
    [switch]$Pause,

    # Skip advancing entirely; leave the backend paused at tick -1.
    [switch]$NoAdvance
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot

function Stop-Port([int]$Port) {
    $conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if ($conns) {
        $conns | ForEach-Object {
            Write-Host "  stopping PID $($_.OwningProcess) on port $Port"
            try { Stop-Process -Id $_.OwningProcess -Force } catch {}
        }
    } else {
        Write-Host "  nothing listening on $Port"
    }
}

if ($Stop) {
    Write-Host "Stopping stack..."
    Stop-Port $BackendPort
    Stop-Port $FrontendPort
    exit 0
}

# --- preflight -------------------------------------------------------------
Write-Host "Preflight..."

$train = Join-Path $Root "data\CMaps\train_FD001.txt"
if (-not (Test-Path $train)) {
    Write-Host "  MISSING: data\CMaps\train_FD001.txt" -ForegroundColor Red
    Write-Host "  data/ is gitignored - download C-MAPSS FD001 yourself." -ForegroundColor Red
    exit 1
}
Write-Host "  C-MAPSS data present"

$scenario = Join-Path $Root "data\scenarios\default.csv"
if (-not (Test-Path $scenario)) {
    Write-Host "  building scenario CSV..."
    python (Join-Path $Root "sim\build_scenario.py") | Out-Null
}
Write-Host "  scenario present"

if (-not (Test-Path (Join-Path $Root "ml\model.pkl"))) {
    Write-Host "  MISSING ml\model.pkl - run: python ml\train.py" -ForegroundColor Red
    exit 1
}
Write-Host "  trained model present"

if (-not (Test-Path (Join-Path $Root "frontend\node_modules"))) {
    Write-Host "  installing frontend deps (first run only)..."
    Push-Location (Join-Path $Root "frontend"); npm install; Pop-Location
}
Write-Host "  frontend deps present"

# --- start -----------------------------------------------------------------
Stop-Port $BackendPort
Stop-Port $FrontendPort

Write-Host ""
Write-Host "Starting backend on $BackendPort..."
Start-Process -FilePath "python" `
    -ArgumentList "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "$BackendPort" `
    -WorkingDirectory $Root -WindowStyle Minimized

$ok = $false
foreach ($i in 1..40) {
    Start-Sleep -Seconds 1
    try {
        $r = Invoke-RestMethod "http://127.0.0.1:$BackendPort/api/health" -TimeoutSec 2
        Write-Host "  backend up: ml=$($r.modules.ml) decision=$($r.modules.decision) sim=$($r.modules.sim) model_loaded=$($r.model_loaded)"
        $ok = $true
        break
    } catch { }
}
if (-not $ok) { Write-Host "  backend did NOT come up" -ForegroundColor Red; exit 1 }

Write-Host "Starting frontend on $FrontendPort..."
Start-Process -FilePath "cmd" `
    -ArgumentList "/c", "npm", "run", "dev", "--", "--port", "$FrontendPort", "--host", "127.0.0.1" `
    -WorkingDirectory (Join-Path $Root "frontend") -WindowStyle Minimized

foreach ($i in 1..40) {
    Start-Sleep -Seconds 1
    try {
        Invoke-WebRequest "http://127.0.0.1:$FrontendPort/" -TimeoutSec 2 -UseBasicParsing | Out-Null
        Write-Host "  frontend up"
        break
    } catch { }
}

# --- demo state ------------------------------------------------------------
if (-not $NoAdvance) {
    Write-Host ""
    Write-Host "Advancing simulation to tick $Tick..."
    $api = "http://127.0.0.1:$BackendPort"
    try {
        Invoke-RestMethod -Method Post "$api/api/sim/start" -TimeoutSec 10 | Out-Null
        Invoke-RestMethod -Method Post "$api/api/sim/jump" -ContentType "application/json" `
            -Body "{`"tick`":$Tick}" -TimeoutSec 30 | Out-Null

        if ($Pause) {
            Invoke-RestMethod -Method Post "$api/api/sim/pause" -TimeoutSec 10 | Out-Null
            Write-Host "  PAUSED at tick $Tick -- the dashboard will not move"
        } else {
            $secs = [math]::Round((361 - $Tick) / 1.0)
            Write-Host "  RUNNING from tick $Tick (~1 tick/sec)"
            Write-Host "  ~$secs sec until the scenario ends and all units read CRITICAL"
        }

        $fleet = Invoke-RestMethod "$api/api/fleet" -TimeoutSec 15
        Write-Host ""
        Write-Host ("  {0,-8}{1,-22}{2,5}{3,8}{4,10}{5,5}  {6}" -f `
            "unit", "name", "cyc", "rul", "risk", "pri", "action")
        foreach ($u in ($fleet.units | Sort-Object rul)) {
            Write-Host ("  {0,-8}{1,-22}{2,5}{3,8:N1}{4,10}{5,5}  {6}" -f `
                $u.unit_id, $u.unit_name, $u.cycle, $u.rul, $u.risk_level, $u.priority, $u.action_code)
        }

        $levels = ($fleet.units | Select-Object -ExpandProperty risk_level | Sort-Object -Unique)
        Write-Host ""
        Write-Host "  risk levels on screen: $($levels -join ', ')"
        if ($levels.Count -lt 2) {
            Write-Host "  WARNING: only one risk level -- poor demo state. Try a different -Tick." -ForegroundColor Yellow
        }
    } catch {
        Write-Host "  could not set demo state: $_" -ForegroundColor Yellow
        Write-Host "  the stack is still up; advance it manually if needed." -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "  Dashboard : http://127.0.0.1:$FrontendPort"
Write-Host "  API       : http://127.0.0.1:$BackendPort/api/health"
Write-Host ""
Write-Host "  .\run_all.ps1              running from tick $Tick, dashboard moves"
Write-Host "  .\run_all.ps1 -Pause       freeze the opening state instead"
Write-Host "  .\run_all.ps1 -Tick 240    3 critical units, more urgent-looking"
Write-Host "  .\run_all.ps1 -NoAdvance   leave paused at tick -1 (empty fleet)"
Write-Host "  .\run_all.ps1 -Stop        stop everything"
Write-Host ""
Write-Host "  Mid-demo, to jump back to a good spread without restarting:"
# Single-quoted so PowerShell does not eat the JSON quotes, then interpolated.
$jumpBody = '{"tick":160}'
Write-Host "    Invoke-RestMethod -Method Post http://127.0.0.1:$BackendPort/api/sim/jump -ContentType application/json -Body '$jumpBody'"
Write-Host ""
Write-Host "  Keep this window open -- closing it may take the servers with it."
