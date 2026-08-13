# 一键重启 agent-harness 后端（8001 端口）
# 用法：在项目根目录 PowerShell 执行  .\restart-backend.ps1

$ErrorActionPreference = "Continue"

# 1. 杀掉占用 8001 的 python 进程
Get-NetTCPConnection -LocalPort 8001 -ErrorAction SilentlyContinue | ForEach-Object {
    $pid = $_.OwningProcess
    try {
        Stop-Process -Id $pid -Force -ErrorAction Stop
        Write-Host "已停止占用 8001 的进程 PID=$pid" -ForegroundColor Green
    } catch {
        Write-Host "无法停止 PID=$pid : $_" -ForegroundColor Yellow
    }
}

# 2. 额外尝试停止所有 uvicorn / python 进程（仅停止包含 app.main 命令行的）
Get-WmiObject Win32_Process | Where-Object { $_.CommandLine -and ($_.CommandLine -like "*uvicorn*app.main*") } | ForEach-Object {
    try {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop
        Write-Host "已停止 uvicorn 进程 PID=$($_.ProcessId)" -ForegroundColor Green
    } catch {
        Write-Host "无法停止 uvicorn PID=$($_.ProcessId) : $_" -ForegroundColor Yellow
    }
}

Start-Sleep -Seconds 2

# 3. 确认端口释放
$still = Get-NetTCPConnection -LocalPort 8001 -ErrorAction SilentlyContinue
if ($still) {
    Write-Host "8001 仍被占用，请手动打开任务管理器结束 python.exe 后重试" -ForegroundColor Red
    exit 1
}

# 4. 加载环境变量
$envFile = Join-Path $PSScriptRoot ".env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match "^\s*([^#][^=]+?)\s*=\s*(.*?)\s*$") {
            [System.Environment]::SetEnvironmentVariable($matches[1], $matches[2], "Process")
        }
    }
    Write-Host "已加载 .env" -ForegroundColor Green
}

# 5. 启动新后端
$backendDir = Join-Path $PSScriptRoot "agent-harness" "backend"
Push-Location $backendDir
Write-Host "启动后端: $backendDir" -ForegroundColor Green
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
Pop-Location
