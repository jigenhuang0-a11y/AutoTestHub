@echo off
chcp 65001 >nul
echo ============================================
echo   AI测试平台 + Agent Harness 运维中台
echo ============================================
echo.
echo 启动方式：
echo.
echo   1. Docker Compose（推荐，一键启动）：
echo      docker compose up -d
echo      访问: 测试平台 http://localhost
echo           运维中台 http://localhost:8080
echo.
echo   2. 本地开发模式（手动逐个启动）：
echo.
echo ============================================
echo   本地开发模式
echo ============================================

:: 检查 Python 是否安装
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [错误] 未找到 Python，请先安装 Python 3.8+
    pause
    exit /b 1
)

:: 检查 Node.js 是否安装
where node >nul 2>nul
if %errorlevel% neq 0 (
    echo [错误] 未找到 Node.js，请先安装 Node.js 16+
    pause
    exit /b 1
)

echo [1/4] 启动后端 Django 服务器 (端口 8000)...
start "后端服务器" cmd /k "cd /d %~dp0backend && echo 正在启动后端服务... && python manage.py runserver 0.0.0.0:8000"

timeout /t 3 >nul

echo [2/4] 启动 AI测试平台 前端 Vue 服务器 (端口 5173)...
start "AI测试平台前端" cmd /k "cd /d %~dp0frontend && echo 正在启动前端服务... && npm run dev"

timeout /t 3 >nul

echo [3/4] 启动 Agent Harness 运维中台 前端 (端口 5174)...
start "Agent Harness 运维中台" cmd /k "cd /d %~dp0agent-harness\frontend && echo 正在启动 Agent Harness 运维中台... && npm run dev"

timeout /t 3 >nul

echo [4/4] 启动 Agent Harness 底座后端 (端口 8001)...
start "Agent Harness 后端" cmd /k "cd /d %~dp0agent-harness\backend && echo 正在启动底座后端... && uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload"

timeout /t 3 >nul

echo.
echo ============================================
echo   所有服务启动中，请稍候...
echo ============================================
echo.
echo 服务列表：
echo   * 测试平台后端：http://127.0.0.1:8000
echo   * AI测试平台前端：http://localhost:5173
echo   * 底座后端：http://127.0.0.1:8001
echo   * Agent Harness 运维中台：http://localhost:5174
echo.
echo 提示：
echo   - 所有窗口已在新标签页中打开
echo   - 关闭窗口即可停止对应服务
echo   - 生产演示推荐使用: docker compose up -d
echo.
echo ============================================
pause
