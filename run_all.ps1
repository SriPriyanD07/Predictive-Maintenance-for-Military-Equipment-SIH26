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
    [int]$FrontendPort = 5173
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

Write-Host ""
Write-Host "  Dashboard : http://127.0.0.1:$FrontendPort"
Write-Host "  API       : http://127.0.0.1:$BackendPort/api/health"
Write-Host ""
Write-Host "Start the simulation running:"
Write-Host "  Invoke-RestMethod -Method Post http://127.0.0.1:$BackendPort/api/sim/start"
Write-Host ""
Write-Host "Stop everything:  .\run_all.ps1 -Stop"
