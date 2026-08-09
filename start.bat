@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

:: ============================================================
:: AI测试平台 一键快速启动（Windows CMD）
:: 使用: 双击运行，或在终端执行 start.bat
:: 架构: agent-harness 单服务（FastAPI 8001 + Vue 5174）
:: ============================================================

set ROOT=%~dp0
set ROOT=%ROOT:~0,-1%
set LOG_DIR=%ROOT%\tmp\logs
set BACKEND_DIR=%ROOT%\agent-harness\backend
set FRONTEND_DIR=%ROOT%\agent-harness\frontend
set TIMEOUT_SECONDS=180

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

echo.
echo ============================================
echo   AI 测试平台 — 快速启动
echo   架构: agent-harness 单服务
echo ============================================
echo.

echo [1/5] 环境检查...

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] 未找到 Python，请先安装 Python 3.10+
    pause
    exit /b 1
)
for /f "delims=" %%i in ('python --version 2^>^&1') do echo   Python: %%i

where node >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] 未找到 Node.js，请先安装 Node.js 18+
    pause
    exit /b 1
)
for /f "delims=" %%i in ('node --version 2^>^&1') do echo   Node.js: %%i

if not exist "%FRONTEND_DIR%\node_modules" (
    echo   正在安装前端依赖...
    pushd "%FRONTEND_DIR%"
    call npm install
    popd
) else (
    echo   前端依赖: 已安装
)

python -c "import uvicorn, fastapi, pydantic_settings, httpx" >nul 2>nul
if %errorlevel% neq 0 (
    echo   正在安装后端依赖...
    pushd "%BACKEND_DIR%"
    pip install fastapi uvicorn pydantic-settings python-dotenv httpx redis tenacity requests
    popd
) else (
    echo   后端依赖: 已安装
)

echo   检查通过.
echo.

echo [2/5] 清理残留进程...
for %%p in (8001 5174) do (
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr :%%p') do (
        taskkill /F /PID %%a >nul 2>nul
        echo   已释放端口 %%p (PID %%a)
    )
)
timeout /t 1 >nul

echo.
echo [3/5] 启动服务...
echo   启动 Agent-Harness 后端 (端口 8001)...
start "Agent-Harness-Backend" cmd /k "cd /d %BACKEND_DIR% && set PORT=8001 && set JWT_SIGNING_KEY=dev-local-signing-key-change-me && uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload"

timeout /t 2 >nul

echo   启动 Agent-Harness 前端 (端口 5174)...
start "Agent-Harness-Frontend" cmd /k "cd /d %FRONTEND_DIR% && npm run dev"

timeout /t 3 >nul

echo.
echo [4/5] 等待服务就绪...
set READY_BACK=0
set READY_FRONT=0
set ELAPSED=0
:wait_loop
if %READY_BACK%==1 if %READY_FRONT%==1 goto ready_done

if %ELAPSED% geq %TIMEOUT_SECONDS% goto wait_timeout

if %READY_BACK%==0 (
    curl -s -o nul -w "%%{http_code}" http://127.0.0.1:8001/api/v1/health > "%LOG_DIR%\_back.code" 2>nul
    set /p BACK_CODE=<"%LOG_DIR%\_back.code"
    if "!BACK_CODE!"=="200" (
        set READY_BACK=1
        echo   后端已就绪 (%ELAPSED%s)
    )
)

if %READY_FRONT%==0 (
    curl -s -o nul -w "%%{http_code}" http://127.0.0.1:5174 > "%LOG_DIR%\_front.code" 2>nul
    set /p FRONT_CODE=<"%LOG_DIR%\_front.code"
    if "!FRONT_CODE!"=="200" (
        set READY_FRONT=1
        echo   前端已就绪 (%ELAPSED%s)
    ) else if "!FRONT_CODE!"=="301" (
        set READY_FRONT=1
        echo   前端已就绪 (%ELAPSED%s)
    )
)

timeout /t 2 >nul
set /a ELAPSED+=2
if %ELAPSED% % 15 lss 2 (
    echo   等待中... (%ELAPSED%/%TIMEOUT_SECONDS%s)
)
goto wait_loop

:ready_done
echo.
echo [5/5] 服务已就绪！
goto summary

:wait_timeout
echo   [WARNING] 等待超时，部分服务可能未就绪。

:summary
echo.
echo ============================================
echo   服务地址
echo ============================================
echo   Agent-Harness 中台:  http://localhost:5174
echo   Harness 底座 API:    http://localhost:8001
echo   健康检查:            http://localhost:8001/api/v1/health
echo.
echo   默认账号: admin / admin123456
echo   日志目录: %LOG_DIR%
echo ============================================
echo.
echo 提示:
echo   - 服务运行在独立的 CMD 窗口中，关闭本窗口不会停止服务
echo   - 如需停止服务，请运行 stop-fast.ps1 或关闭对应窗口
echo.
pause
endlocal
