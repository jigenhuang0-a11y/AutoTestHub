# ============================================================
# AI 测试平台 — 一键启动 / 停止（Windows PowerShell）
# 双击可直接运行；若系统限制，请在 PowerShell 中先执行：
#   Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned -Force
# 用法:
#   启动:  .\run.ps1
#   停止:  .\run.ps1 -Stop
#   仅重启后端: .\run.ps1 -RestartBackend
# ============================================================
param(
    [switch]$Stop,
    [switch]$RestartBackend
)

# 尝试自动绕过当前会话执行策略限制（双击运行时常见）
try {
    if ($ExecutionContext.SessionState.LanguageMode -ne "FullLanguage") {
        Write-Host "[错误] PowerShell 语言模式受限，无法运行脚本" -ForegroundColor Red
        Read-Host "按 Enter 退出"
        exit 1
    }
} catch { }

$ErrorActionPreference = "Stop"
$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
$LOG_DIR = Join-Path $ROOT "tmp\logs"
$BACKEND_DIR = Join-Path $ROOT "agent-harness" "backend"
$FRONTEND_DIR = Join-Path $ROOT "agent-harness" "frontend"
$BACK_PORT = 8001
$FRONT_PORT = 5174
$ENV_FILE = Join-Path $ROOT ".env"

# ---------- 加载 .env 中的环境变量（供后端使用） ----------
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

# ---------- 停止所有相关进程 ----------
function Stop-AllServices {
    $stopped = 0
    # 1. 按端口找进程
    foreach ($port in @($BACK_PORT, $FRONT_PORT)) {
        Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue | ForEach-Object {
            try {
                $p = Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue
                if ($p) { Stop-Process -Id $p.Id -Force; $stopped++; Write-Host "  已释放端口 $port (PID $($p.Id))" -ForegroundColor Green }
            } catch { }
        }
    }
    # 2. 按命令行特征找 uvicorn / vite 进程（兜底）
    Get-Process -ErrorAction SilentlyContinue | Where-Object {
        $_.ProcessName -in @("python", "pythonw", "node") -and $_.CommandLine -match "uvicorn app.main|vite"
    } | ForEach-Object {
        try {
            Stop-Process -Id $_.Id -Force; $stopped++; Write-Host "  已停止 $($_.ProcessName) (PID $($_.Id))" -ForegroundColor Green
        } catch { }
    }
    return $stopped
}

# ---------- 等待端口就绪 ----------
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

# ============================================================
# 停止模式
# ============================================================
if ($Stop) {
    Write-Host "`n[停止] 正在停止 AI 测试平台服务..." -ForegroundColor Cyan
    $n = Stop-AllServices
    if ($n -eq 0) { Write-Host "  没有发现运行中的服务" -ForegroundColor Gray }
    else { Write-Host "  共停止 $n 个进程" -ForegroundColor Green }
    Start-Sleep -Seconds 1
    Write-Host "[完成] 服务已停止`n" -ForegroundColor Cyan
    exit 0
}

# ============================================================
# 仅重启后端
# ============================================================
if ($RestartBackend) {
    Write-Host "`n[重启后端] 停止后端进程..." -ForegroundColor Cyan
    Get-NetTCPConnection -LocalPort $BACK_PORT -ErrorAction SilentlyContinue | ForEach-Object {
        try { Stop-Process -Id $_.OwningProcess -Force; Write-Host "  已停止后端 PID $($_.OwningProcess)" -ForegroundColor Green } catch { }
    }
    Start-Sleep -Seconds 2
    Import-Env
    $env:PORT = $BACK_PORT
    Start-Process -FilePath "python" -ArgumentList "-m","uvicorn","app.main:app","--host","0.0.0.0","--port",$BACK_PORT,"--reload" `
        -WorkingDirectory $BACKEND_DIR -WindowStyle Normal
    Write-Host "[启动] 后端正在启动 (http://localhost:$BACK_PORT)..." -ForegroundColor Green
    exit 0
}

# ============================================================
# 启动模式（默认）
# ============================================================
Write-Host "`n============================================" -ForegroundColor Cyan
Write-Host "  AI 测试平台 — 启动" -ForegroundColor Cyan
Write-Host "============================================`n" -ForegroundColor Cyan

# 0. 前置清理
Write-Host "[1/4] 清理残留进程..." -ForegroundColor Yellow
Stop-AllServices | Out-Null

# 1. 环境检查
Write-Host "[2/4] 环境检查..." -ForegroundColor Yellow
if (-not (Get-Command python -ErrorAction SilentlyContinue)) { Write-Host "[错误] 未找到 python，请安装 Python 3.10+" -ForegroundColor Red; exit 1 }
if (-not (Get-Command node -ErrorAction SilentlyContinue)) { Write-Host "[错误] 未找到 node，请安装 Node.js 18+" -ForegroundColor Red; exit 1 }
Write-Host "  Python: $(python --version 2>&1)  Node: $(node --version)"

if (-not (Test-Path (Join-Path $FRONTEND_DIR "node_modules"))) {
    Write-Host "  安装前端依赖..." -ForegroundColor Gray
    Push-Location $FRONTEND_DIR; & npm install; Pop-Location
} else {
    Write-Host "  前端依赖: 已安装"
}

# 2. 启动服务
Write-Host "[3/4] 启动服务..." -ForegroundColor Yellow
Import-Env
$env:PORT = $BACK_PORT

# 后端（从 .env 读取 JWT_SIGNING_KEY / SERVICE_TOKEN）
Start-Process -FilePath "python" -ArgumentList "-m","uvicorn","app.main:app","--host","0.0.0.0","--port",$BACK_PORT,"--reload" `
    -WorkingDirectory $BACKEND_DIR -WindowStyle Normal
Write-Host "  后端启动中 (http://localhost:$BACK_PORT)" -ForegroundColor Green

Start-Sleep -Seconds 2

# 前端
Start-Process -FilePath "npm" -ArgumentList "run","dev" `
    -WorkingDirectory $FRONTEND_DIR -WindowStyle Normal
Write-Host "  前端启动中 (http://localhost:$FRONT_PORT)" -ForegroundColor Green

# 3. 等待就绪
Write-Host "[4/4] 等待服务就绪..." -ForegroundColor Yellow
$backReady = Wait-Port $BACK_PORT
$frontReady = Wait-Port $FRONT_PORT

Write-Host "`n============================================" -ForegroundColor Cyan
Write-Host "  服务地址" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  AI 测试平台:    http://localhost:$FRONT_PORT" -ForegroundColor White
Write-Host "  API 底座:       http://localhost:$BACK_PORT" -ForegroundColor White
Write-Host "  健康检查:       http://localhost:$BACK_PORT/api/v1/health" -ForegroundColor Gray
Write-Host "  默认账号:       admin / admin123456" -ForegroundColor Gray
Write-Host "============================================`n" -ForegroundColor Cyan

if (-not $backReady) { Write-Host "  [警告] 后端未在预期时间内就绪，请查看弹出的 python 窗口日志" -ForegroundColor Red }
if (-not $frontReady) { Write-Host "  [警告] 前端未在预期时间内就绪，请查看弹出的 node 窗口日志" -ForegroundColor Red }

Write-Host "  后端/前端已在独立窗口运行。停止请运行: .\run.ps1 -Stop`n" -ForegroundColor Gray
