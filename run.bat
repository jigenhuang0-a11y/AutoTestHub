@echo off
chcp 65001 >nul 2>&1
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
