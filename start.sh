#!/bin/bash
# ============================================================
# AI测试平台 一键快速启动（Linux/macOS）
# 使用: ./start.sh
# 架构: agent-harness 单服务（FastAPI 8001 + Vue 5174）
# ============================================================
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$ROOT/tmp/logs"
BACKEND_DIR="$ROOT/agent-harness/backend"
FRONTEND_DIR="$ROOT/agent-harness/frontend"
TIMEOUT_SECONDS=180

mkdir -p "$LOG_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo ""
echo "============================================"
echo "  AI 测试平台 — 快速启动"
echo "  架构: agent-harness 单服务"
echo "============================================"
echo ""

echo -e "${YELLOW}[1/5] 环境检查...${NC}"
command -v python3 >/dev/null 2>&1 || { echo -e "${RED}[ERROR] 未找到 python3${NC}"; exit 1; }
command -v node >/dev/null 2>&1 || { echo -e "${RED}[ERROR] 未找到 Node.js${NC}"; exit 1; }

echo -e "  Python: $(python3 --version)"
echo -e "  Node.js: $(node --version)"

if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
    echo -e "  正在安装前端依赖..."
    (cd "$FRONTEND_DIR" && npm install)
else
    echo -e "  前端依赖: 已安装"
fi

if ! python3 -c "import uvicorn, fastapi, pydantic_settings, httpx" >/dev/null 2>&1; then
    echo -e "  正在安装后端依赖..."
    (cd "$BACKEND_DIR" && pip3 install fastapi uvicorn pydantic-settings python-dotenv httpx redis tenacity requests)
else
    echo -e "  后端依赖: 已安装"
fi

echo -e "  ${GREEN}检查通过.${NC}"

echo ""
echo -e "${YELLOW}[2/5] 清理残留进程...${NC}"
for port in 8001 5174; do
    pid=$(lsof -ti :$port 2>/dev/null || true)
    if [ -n "$pid" ]; then
        kill -9 $pid >/dev/null 2>&1 || true
        echo -e "  已释放端口 $port (PID $pid)"
    fi
done
sleep 1

echo ""
echo -e "${YELLOW}[3/5] 启动服务...${NC}"
echo -e "  启动 Agent-Harness 后端 (端口 8001)..."
nohup bash -c "cd '$BACKEND_DIR' && export PORT=8001 && export JWT_SIGNING_KEY='dev-local-signing-key-change-me' && uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload" > "$LOG_DIR/agent-harness-backend.log" 2>&1 &
BACK_PID=$!

sleep 2

echo -e "  启动 Agent-Harness 前端 (端口 5174)..."
nohup bash -c "cd '$FRONTEND_DIR' && npm run dev" > "$LOG_DIR/agent-harness-frontend.log" 2>&1 &
FRONT_PID=$!

# 停止函数
cleanup() {
    echo ""
    echo -e "${YELLOW}正在停止服务...${NC}"
    kill $BACK_PID $FRONT_PID >/dev/null 2>&1 || true
    wait $BACK_PID $FRONT_PID >/dev/null 2>&1 || true
    echo -e "${GREEN}已停止。${NC}"
    exit 0
}
trap cleanup INT TERM EXIT

sleep 3

echo ""
echo -e "${YELLOW}[4/5] 等待服务就绪...${NC}"
READY_BACK=0
READY_FRONT=0
ELAPSED=0

while [ $READY_BACK -eq 0 ] || [ $READY_FRONT -eq 0 ]; do
    if [ $ELAPSED -ge $TIMEOUT_SECONDS ]; then
        echo -e "  ${YELLOW}[WARNING] 等待超时，部分服务可能未就绪。${NC}"
        break
    fi

    if [ $READY_BACK -eq 0 ]; then
        code=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8001/api/v1/health 2>/dev/null || echo "000")
        if [ "$code" = "200" ]; then
            READY_BACK=1
            echo -e "  ${GREEN}后端已就绪 (${ELAPSED}s)${NC}"
        fi
    fi

    if [ $READY_FRONT -eq 0 ]; then
        code=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:5174 2>/dev/null || echo "000")
        if [ "$code" = "200" ] || [ "$code" = "301" ]; then
            READY_FRONT=1
            echo -e "  ${GREEN}前端已就绪 (${ELAPSED}s)${NC}"
        fi
    fi

    sleep 2
    ELAPSED=$((ELAPSED + 2))
    if [ $((ELAPSED % 15)) -lt 2 ]; then
        echo -e "  等待中... (${ELAPSED}/${TIMEOUT_SECONDS}s)"
    fi
done

echo ""
echo -e "${YELLOW}[5/5] 服务状态${NC}"
echo ""
echo -e "${CYAN}============================================${NC}"
echo -e "  ${CYAN}服务地址${NC}"
echo -e "${CYAN}============================================${NC}"
echo -e "  Agent-Harness 中台:  http://localhost:5174"
echo -e "  Harness 底座 API:    http://localhost:8001"
echo -e "  健康检查:            http://localhost:8001/api/v1/health"
echo ""
echo -e "  默认账号: admin / admin123456"
echo -e "  日志目录: $LOG_DIR"
echo -e "${CYAN}============================================${NC}"
echo ""
echo "提示:"
echo "  - 按 Ctrl+C 停止所有服务"
echo "  - 日志保存在 $LOG_DIR"
echo ""

wait
