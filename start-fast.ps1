# ============================================================
# AI测试平台 一键快速启动（Windows PowerShell）
# 使用: 右键 -> 使用 PowerShell 运行, 或在终端执行 .\start-fast.ps1
# ============================================================
$ErrorActionPreference = "Stop"
$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
$TIMEOUT_SECONDS = 180
$START_TIME = Get-Date

$LOG_DIR = "$ROOT\tmp\logs"
$TMP_DIR = "$ROOT\tmp"
if (-not (Test-Path $LOG_DIR)) { New-Item -ItemType Directory -Path $LOG_DIR -Force | Out-Null }

Write-Host "`n============================================" -ForegroundColor Cyan
Write-Host "  AI 测试平台 — 快速启动" -ForegroundColor Cyan
Write-Host "  目标: 3 分钟内全部就绪" -ForegroundColor Cyan
Write-Host "============================================`n" -ForegroundColor Cyan

Write-Host "[1/5] 前置检查..." -ForegroundColor Yellow

$CHECK_ITEMS = @()
if (-not (Test-Path "$ROOT\frontend\node_modules")) {
    $CHECK_ITEMS += "frontend/node_modules"
}
if (-not (Test-Path "$ROOT\agent-harness\frontend\node_modules")) {
    $CHECK_ITEMS += "agent-harness/frontend/node_modules"
}

if ($CHECK_ITEMS.Count -gt 0) {
    Write-Host "  缺少依赖，正在安装..." -ForegroundColor Magenta
    foreach ($item in $CHECK_ITEMS) {
        $dir = Split-Path -Parent "$ROOT\$item"
        Write-Host "  npm install -> $dir" -ForegroundColor Gray
        Push-Location $dir
        npm install 2>&1 | Out-Null
        Pop-Location
    }
}

$PYTHON_CMD = "python"
$pyInfo = & $PYTHON_CMD --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "  [ERROR] Python 未找到！" -ForegroundColor Red
    exit 1
}
Write-Host "  Python: $pyInfo" -ForegroundColor Gray

Push-Location "$ROOT\backend"
$djangoCheck = & $PYTHON_CMD -c "import django; print(django.VERSION[0],django.VERSION[1])" 2>&1
Pop-Location
if ($LASTEXITCODE -eq 0) {
    Write-Host "  Django: $djangoCheck" -ForegroundColor Gray
} else {
    Write-Host "  [ERROR] Django 未安装！运行: cd backend && pip install -r requirements.txt" -ForegroundColor Red
    exit 1
}

$harnessDepCheck = & $PYTHON_CMD -c "import uvicorn, fastapi, pydantic_settings, httpx; print('OK')" 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "  Agent-Harness dep: OK" -ForegroundColor Gray
} else {
    Write-Host "  [WARN] Agent-Harness 缺少依赖，正在安装..." -ForegroundColor Magenta
    Push-Location "$ROOT\agent-harness\backend"
    pip install fastapi uvicorn pydantic-settings python-dotenv httpx redis tenacity requests 2>&1 | Select-Object -Last 3
    Pop-Location
}

$PRE_TIME = [math]::Round(((Get-Date) - $START_TIME).TotalSeconds, 1)
Write-Host "  检查通过 (${PRE_TIME}s)`n" -ForegroundColor Green

Write-Host "[2/5] 清理残留服务..." -ForegroundColor Yellow
$ports = @(8000, 8001, 5173, 5174)
foreach ($port in $ports) {
    try {
        $conn = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
        if ($conn) {
            $conn | ForEach-Object {
                try { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } catch {}
            }
            Write-Host "  已释放端口 $port" -ForegroundColor Gray
        }
    } catch {}
}
Start-Sleep -Seconds 1

Write-Host "`n[3/5] 并行启动 4 个服务..." -ForegroundColor Yellow

function Start-ServiceWindow($title, $dir, $cmd, $logFile) {
    $scriptPath = "$TMP_DIR\start-$title.ps1"
    $scriptBody = @"
cd '$dir'
`$Host.UI.RawUI.WindowTitle = '$title'
Write-Host '[启动中] $title' -ForegroundColor Cyan
$cmd 2>&1 | Tee-Object -FilePath '$logFile'
"@
    $scriptBody | Out-File -FilePath $scriptPath -Encoding utf8 -Force
    Start-Process powershell -ArgumentList @("-NoProfile", "-NoExit", "-File", $scriptPath) -WindowStyle Normal
    Write-Host "  已启动: $title" -ForegroundColor Gray
}

Start-ServiceWindow "Agent-Harness-Backend" "$ROOT\agent-harness\backend" "`$env:PORT='8001'; uvicorn app.main:app --host 0.0.0.0 --port 8001" "$LOG_DIR\agent-harness-backend.log"
Start-ServiceWindow "Agent-Harness-Frontend" "$ROOT\agent-harness\frontend" "npm run dev" "$LOG_DIR\agent-harness-frontend.log"
Start-ServiceWindow "Django-Backend" "$ROOT\backend" "`$env:AI_ORCHESTRATION_SERVICE_URL='http://localhost:8001'; python manage.py runserver 0.0.0.0:8000 --noreload" "$LOG_DIR\django-backend.log"
Start-ServiceWindow "AI-Platform-Frontend" "$ROOT\frontend" "npm run dev" "$LOG_DIR\ai-platform-frontend.log"

Write-Host "  4 个服务窗口已启动`n" -ForegroundColor Green

Write-Host "[4/5] 等待服务就绪..." -ForegroundColor Yellow

$services = @(
    @{Name="Agent-Harness 底座";  URL="http://127.0.0.1:8001/api/v1/health"; Ready=$false},
    @{Name="Django 后端";          URL="http://127.0.0.1:8000/api/auth/login/"; Ready=$false; Method="POST"; Body='{"username":"admin","password":"dummy"}'},
    @{Name="Agent-Harness 前端";   URL="http://127.0.0.1:5174"; Ready=$false},
    @{Name="AI平台前端";           URL="http://127.0.0.1:5173"; Ready=$false}
)

$ELAPSED = 0
$CHECK_INTERVAL = 2
Start-Sleep -Seconds 3

do {
    foreach ($svc in $services) {
        if ($svc.Ready) { continue }
        try {
            $method = if ($svc.Method) { $svc.Method } else { 'GET' }
            $body = if ($svc.Body) { $svc.Body } else { $null }
            $resp = if ($body) {
                Invoke-WebRequest -Uri $svc.URL -Method $method -Body $body -ContentType "application/json" -TimeoutSec 3 -ErrorAction Stop
            } else {
                Invoke-WebRequest -Uri $svc.URL -Method $method -TimeoutSec 3 -ErrorAction Stop
            }
            if ($resp.StatusCode -lt 500) {
                $svc.Ready = $true
                $elapsed = [math]::Round(((Get-Date) - $START_TIME).TotalSeconds, 0)
                Write-Host "  $($svc.Name) 就绪 (${elapsed}s)" -ForegroundColor Green
            }
        } catch {}
    }

    $allReady = ($services | Where-Object { -not $_.Ready }).Count -eq 0
    if ($allReady) { break }

    Start-Sleep -Seconds $CHECK_INTERVAL
    $ELAPSED = [math]::Round(((Get-Date) - $START_TIME).TotalSeconds, 0)

    if ($ELAPSED % 15 -lt $CHECK_INTERVAL) {
        $waiting = ($services | Where-Object { -not $_.Ready } | ForEach-Object { $_.Name }) -join ", "
        Write-Host "  等待中 ($ELAPSED`s): $waiting" -ForegroundColor Gray
    }
} while ($ELAPSED -lt $TIMEOUT_SECONDS)

Write-Host "`n[5/5] 汇总..." -ForegroundColor Yellow

$notReady = $services | Where-Object { -not $_.Ready }
$TOTAL_TIME = [math]::Round(((Get-Date) - $START_TIME).TotalSeconds, 0)

if ($notReady.Count -eq 0) {
    Write-Host "`n  ============================================" -ForegroundColor Green
    Write-Host "  全部启动成功！耗时: ${TOTAL_TIME}秒" -ForegroundColor Green
    Write-Host "  ============================================" -ForegroundColor Green
} else {
    Write-Host "`n  [WARNING] 以下服务未在 ${TIMEOUT_SECONDS}s 内就绪:" -ForegroundColor Yellow
    foreach ($s in $notReady) {
        Write-Host "    - $($s.Name): $($s.URL)" -ForegroundColor Yellow
    }
    Write-Host "`n  请查看对应窗口或日志文件排查: $LOG_DIR" -ForegroundColor Yellow
}

Write-Host "`n  ┌──────────────────────────────────────────────┐" -ForegroundColor Cyan
Write-Host "  │  服务                地址                    │" -ForegroundColor Cyan
Write-Host "  ├──────────────────────────────────────────────┤" -ForegroundColor Cyan
Write-Host "  │  AI测试平台前端       http://localhost:5173   │" -ForegroundColor Cyan
Write-Host "  │  Agent-Harness中台    http://localhost:5174   │" -ForegroundColor Cyan
Write-Host "  │  Django 后端 API       http://localhost:8000   │" -ForegroundColor Cyan
Write-Host "  │  Harness 底座 API      http://localhost:8001   │" -ForegroundColor Cyan
Write-Host "  ├──────────────────────────────────────────────┤" -ForegroundColor Cyan
Write-Host "  │  默认账号: admin / admin123456               │" -ForegroundColor Cyan
Write-Host "  │  日志目录: $LOG_DIR" -ForegroundColor Cyan
Write-Host "  └──────────────────────────────────────────────┘" -ForegroundColor Cyan

if ($notReady.Count -eq 0) {
    Start-Process "http://localhost:5173"
    Start-Sleep -Milliseconds 500
    Start-Process "http://localhost:5174"
}

Write-Host "`n提示:" -ForegroundColor Magenta
Write-Host "  - 关闭本窗口不会停止服务（服务在独立窗口运行）" -ForegroundColor Gray
Write-Host "  - 按 [Enter] 停止所有服务并退出" -ForegroundColor Gray
Write-Host "  - 如需单独停止，请运行 .\stop-fast.ps1`n" -ForegroundColor Gray

Read-Host "按 Enter 停止所有服务并退出"

Write-Host "`n正在停止服务..." -ForegroundColor Yellow
& "$ROOT\stop-fast.ps1"
Write-Host "已退出。" -ForegroundColor Green
