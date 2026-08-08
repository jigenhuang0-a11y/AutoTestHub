@echo off
chcp 65001 >nul
echo ============================================
echo   Agent Harness - 一键启动脚本
echo ============================================
echo.

::: 检查 Python 是否安装
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [错误] 未找到 Python，请先安装 Python 3.8+
    pause
    exit /b 1
)

::: 检查 Node.js 是否安装
where node >nul 2>nul
if %errorlevel% neq 0 (
    echo [错误] 未找到 Node.js，请先安装 Node.js 16+
    pause
    exit /b 1
)

echo [1/2] 启动底座后端服务 (端口 8001)...
start "Agent Harness 后端" cmd /k "cd /d %~dp0backend && echo 正在启动编排底座... && uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload"

timeout /t 3 >nul

echo [2/2] 启动底座前端服务 (端口 5174)...
start "Agent Harness 前端" cmd /k "cd /d %~dp0frontend && echo 正在启动运维中台... && npm run dev"

timeout /t 3 >nul

echo.
echo ============================================
echo   Agent Harness 服务启动中，请稍候...
echo ============================================
echo.
echo 服务列表：
echo   ✓ 后端服务：http://127.0.0.1:8001
echo   ✓ 前端服务：http://localhost:5174
echo.
echo 提示：
echo   - 关闭窗口即可停止对应服务
echo   - 浏览器访问：http://localhost:5174
echo.
echo ============================================
pause
