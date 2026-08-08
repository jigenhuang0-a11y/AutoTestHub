@echo off
chcp 65001 >nul
cd /d "%~dp0\.."
echo ========================================
echo   AutoTestHub - Auto Screenshot Tool
echo ========================================
echo.
echo [*] Target: http://8.163.86.47
echo [*] Taking screenshots...
echo.
python -u scripts\take_screenshots.py
echo.
echo [Done] Check docs\screenshots\ folder
pause
