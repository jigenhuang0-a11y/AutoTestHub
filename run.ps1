# ============================================================
# AI Test Platform One-Click Runner (Windows PowerShell)
# Double-click run.bat to start; run.ps1 itself can also be used.
# Usage:
#   Start:         .\run.ps1
#   Stop:          .\run.ps1 -Stop
#   Restart backend only: .\run.ps1 -RestartBackend
# ============================================================
param(
    [switch]$Stop,
    [switch]$RestartBackend
)

$ErrorActionPreference = "Stop"
$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
$LOG_DIR = Join-Path $ROOT "tmp\logs"
$BACKEND_DIR = Join-Path (Join-Path $ROOT "agent-harness") "backend"
$FRONTEND_DIR = Join-Path (Join-Path $ROOT "agent-harness") "frontend"
$BACK_PORT = 8001
$FRONT_PORT = 5174
$ENV_FILE = Join-Path $ROOT ".env"

function Import-Env {
    if (-not (Test-Path $ENV_FILE)) { return }
    Get-Content $ENV_FILE | ForEach-Object {
        if ($_ -match "^\s*([^#][^=]+?)\s*=\s*(.*?)\s*$") {
            $k = $matches[1].Trim()
            $v = $matches[2].Trim()
            if (-not [string]::IsNullOrEmpty($v)) {
                [System.Environment]::SetEnvironmentVariable($k, $v, "Process")
            }
        }
    }
}

function Stop-AllServices {
    $stopped = 0
    foreach ($port in @($BACK_PORT, $FRONT_PORT)) {
        Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue | ForEach-Object {
            try {
                $p = Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue
                if ($p) { Stop-Process -Id $p.Id -Force; $stopped++; Write-Host "  Released port $port (PID $($p.Id))" -ForegroundColor Green }
            } catch { }
        }
    }
    Get-Process -ErrorAction SilentlyContinue | Where-Object {
        $_.ProcessName -in @("python", "pythonw", "node") -and $_.CommandLine -match "uvicorn app.main|vite"
    } | ForEach-Object {
        try {
            Stop-Process -Id $_.Id -Force; $stopped++; Write-Host "  Stopped $($_.ProcessName) (PID $($_.Id))" -ForegroundColor Green
        } catch { }
    }
    return $stopped
}

function Wait-Port($port, $timeout = 180) {
    $elapsed = 0
    while ($elapsed -lt $timeout) {
        $conn = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
        if ($conn) { return $true }
        Start-Sleep -Seconds 2
        $elapsed += 2
    }
    return $false
}

if ($Stop) {
    Write-Host "`n[Stop] Stopping AI Test Platform services..." -ForegroundColor Cyan
    $n = Stop-AllServices
    if ($n -eq 0) { Write-Host "  No running services found" -ForegroundColor Gray }
    else { Write-Host "  Stopped $n process(es)" -ForegroundColor Green }
    Start-Sleep -Seconds 1
    Write-Host "[Done] Services stopped" -ForegroundColor Cyan
    exit 0
}

if ($RestartBackend) {
    Write-Host "`n[Restart Backend] Stopping backend process..." -ForegroundColor Cyan
    Get-NetTCPConnection -LocalPort $BACK_PORT -ErrorAction SilentlyContinue | ForEach-Object {
        try { Stop-Process -Id $_.OwningProcess -Force; Write-Host "  Stopped backend PID $($_.OwningProcess)" -ForegroundColor Green } catch { }
    }
    Start-Sleep -Seconds 2
    Import-Env
    $env:PORT = $BACK_PORT
    Start-Process -FilePath "python" -ArgumentList "-m","uvicorn","app.main:app","--host","0.0.0.0","--port",$BACK_PORT,"--reload" `
        -WorkingDirectory $BACKEND_DIR -WindowStyle Normal
    Write-Host "[Start] Backend starting at http://localhost:$BACK_PORT ..." -ForegroundColor Green
    exit 0
}

Write-Host "`n============================================" -ForegroundColor Cyan
Write-Host "  AI Test Platform - Start" -ForegroundColor Cyan
Write-Host "============================================`n" -ForegroundColor Cyan

Write-Host "[1/4] Cleaning up stale processes..." -ForegroundColor Yellow
Stop-AllServices | Out-Null

Write-Host "[2/4] Environment check..." -ForegroundColor Yellow
if (-not (Get-Command python -ErrorAction SilentlyContinue)) { Write-Host "[Error] python not found" -ForegroundColor Red; exit 1 }
if (-not (Get-Command node -ErrorAction SilentlyContinue)) { Write-Host "[Error] node not found" -ForegroundColor Red; exit 1 }
Write-Host "  Python: $(python --version 2>&1)  Node: $(node --version)"

if (-not (Test-Path (Join-Path $FRONTEND_DIR "node_modules"))) {
    Write-Host "  Installing frontend dependencies..." -ForegroundColor Gray
    Push-Location $FRONTEND_DIR; & npm install; Pop-Location
} else {
    Write-Host "  Frontend dependencies: OK"
}

Write-Host "[3/4] Starting services..." -ForegroundColor Yellow
Import-Env
$env:PORT = $BACK_PORT

Start-Process -FilePath "python" -ArgumentList "-m","uvicorn","app.main:app","--host","0.0.0.0","--port",$BACK_PORT,"--reload" `
    -WorkingDirectory $BACKEND_DIR -WindowStyle Normal
Write-Host "  Backend starting at http://localhost:$BACK_PORT" -ForegroundColor Green

Start-Sleep -Seconds 2

Start-Process -FilePath "cmd" -ArgumentList "/c","npm","run","dev" `
    -WorkingDirectory $FRONTEND_DIR -WindowStyle Normal
Write-Host "  Frontend starting at http://localhost:$FRONT_PORT" -ForegroundColor Green

Write-Host "[4/4] Waiting for services..." -ForegroundColor Yellow
$backReady = Wait-Port $BACK_PORT
$frontReady = Wait-Port $FRONT_PORT

Write-Host "`n============================================" -ForegroundColor Cyan
Write-Host "  Service URLs" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Web App:        http://localhost:$FRONT_PORT" -ForegroundColor White
Write-Host "  API Base:       http://localhost:$BACK_PORT" -ForegroundColor White
Write-Host "  Health Check:   http://localhost:$BACK_PORT/api/v1/health" -ForegroundColor Gray
Write-Host "  Default Login:  admin / admin123456" -ForegroundColor Gray
Write-Host "============================================`n" -ForegroundColor Cyan

if (-not $backReady) { Write-Host "  [Warning] Backend did not become ready; check the python window" -ForegroundColor Red }
if (-not $frontReady) { Write-Host "  [Warning] Frontend did not become ready; check the node window" -ForegroundColor Red }

Write-Host "  Backend and frontend are running in separate windows." -ForegroundColor Gray
Write-Host "  To stop, run: .\run.ps1 -Stop`n" -ForegroundColor Gray
