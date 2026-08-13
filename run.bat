@echo off
REM ============================================================
REM  AI 测试平台 — 双击启动器（双击 run.bat 即可，无需改 PowerShell 策略）
REM  停止: 双击 run.bat 一次（会先清理旧进程）；或命令行 run.bat stop
REM ============================================================
setlocal
set "ROOT=%~dp0"
set "PS=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"

if /I "%~1"=="stop" (
    "%PS%" -NoProfile -ExecutionPolicy Bypass -File "%ROOT%run.ps1" -Stop
    goto :eof
)
if /I "%~1"=="restartbackend" (
    "%PS%" -NoProfile -ExecutionPolicy Bypass -File "%ROOT%run.ps1" -RestartBackend
    goto :eof
)

"%PS%" -NoProfile -ExecutionPolicy Bypass -File "%ROOT%run.ps1"
goto :eof
