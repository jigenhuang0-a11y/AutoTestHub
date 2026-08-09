# ============================================================
# AI测试平台 一键停止（Windows PowerShell）
# 使用: 右键 -> 使用 PowerShell 运行, 或在终端执行 .\stop-fast.ps1
# ============================================================
$ErrorActionPreference = "SilentlyContinue"
$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "`n============================================" -ForegroundColor Cyan
Write-Host "  AI 测试平台 — 停止服务" -ForegroundColor Cyan
Write-Host "============================================`n" -ForegroundColor Cyan

$stopped = 0

$titles = @("Agent-Harness-Backend", "Agent-Harness-Frontend")
foreach ($title in $titles) {
    $procs = Get-Process | Where-Object { $_.MainWindowTitle -like "*$title*" }
    foreach ($p in $procs) {
        try {
            Stop-Process -Id $p.Id -Force
            Write-Host "  已停止: $($p.MainWindowTitle) (PID: $($p.Id))" -ForegroundColor Green
            $stopped++
        } catch {
            Write-Host "  停止失败: $($p.MainWindowTitle)" -ForegroundColor Red
        }
    }
}

$ports = @(8001, 5174)
foreach ($port in $ports) {
    $conns = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
    foreach ($conn in $conns) {
        try {
            $proc = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
            if ($proc -and ($proc.ProcessName -in @("python", "pythonw", "node", "powershell", "cmd"))) {
                Stop-Process -Id $proc.Id -Force
                Write-Host "  已释放端口 $port (PID: $($proc.Id))" -ForegroundColor Green
                $stopped++
            }
        } catch {}
    }
}

Get-Process | Where-Object { $_.ProcessName -eq "node" -and $_.CommandLine -match "vite" } | ForEach-Object {
    Stop-Process -Id $_.Id -Force
    Write-Host "  已停止 vite 进程 (PID: $($_.Id))" -ForegroundColor Green
    $stopped++
}
Get-Process | Where-Object { $_.ProcessName -eq "python" -and $_.CommandLine -match "uvicorn|manage.py runserver" } | ForEach-Object {
    Stop-Process -Id $_.Id -Force
    Write-Host "  已停止 Python 服务进程 (PID: $($_.Id))" -ForegroundColor Green
    $stopped++
}

if ($stopped -eq 0) {
    Write-Host "  没有发现运行中的服务" -ForegroundColor Gray
} else {
    Write-Host "`n  共停止 $stopped 个服务进程" -ForegroundColor Green
}

Write-Host "`n============================================" -ForegroundColor Cyan
Write-Host "  停止完成" -ForegroundColor Cyan
Write-Host "============================================`n" -ForegroundColor Cyan

Start-Sleep -Seconds 1
