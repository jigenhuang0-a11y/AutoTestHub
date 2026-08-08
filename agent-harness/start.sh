#!/bin/bash
# ============================================================
# Agent Harness — 一键启动 & 健康检查脚本
# 用法: ./start.sh
# ============================================================
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'
CHECK="✓"

echo "========================================="
echo "  Agent Harness - 启动脚本"
echo "========================================="

# --------------------------------------------------
# 1. 启动所有容器
# --------------------------------------------------
echo -e "\n${YELLOW}[1/3] 启动底座容器服务...${NC}"
docker compose up -d --wait 2>/dev/null || docker compose up -d
echo -e "${GREEN}${CHECK} 容器已启动${NC}"

# --------------------------------------------------
# 2. 服务健康检查
# --------------------------------------------------
echo -e "\n${YELLOW}[2/3] 服务健康检查...${NC}"

for srv in agent-harness-redis agent-harness-orchestrator agent-harness-frontend agent-harness-prometheus agent-harness-grafana; do
    status=$(docker inspect --format='{{.State.Status}}' $srv 2>/dev/null || echo "not_found")
    health=$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}no_healthcheck{{end}}' $srv 2>/dev/null || echo "unknown")
    if [ "$status" = "running" ]; then
        if [ "$health" = "healthy" ] || [ "$health" = "no_healthcheck" ]; then
            echo -e "  ${GREEN}${CHECK}${NC} $srv"
        else
            echo -e "  ${YELLOW}⚠${NC} $srv — $health"
        fi
    else
        echo -e "  ${RED}✗${NC} $srv — $status"
    fi
done

# --------------------------------------------------
# 3. 编排服务健康检查
# --------------------------------------------------
echo -e "\n${YELLOW}[3/3] 编排服务接口检查...${NC}"
sleep 3

HEALTH_STATUS=$(curl -sf http://localhost:8001/api/v1/health/live -o /dev/null -w "%{http_code}" 2>/dev/null || echo "000")
if [ "$HEALTH_STATUS" = "200" ]; then
    echo -e "${GREEN}${CHECK} 编排服务健康接口正常 (200)${NC}"
else
    echo -e "${YELLOW}⚠ 编排服务健康接口未就绪 (HTTP $HEALTH_STATUS)，请稍后重试${NC}"
fi

# --------------------------------------------------
# 完成
# --------------------------------------------------
echo ""
echo "========================================="
echo -e "  ${GREEN}🚀 Agent Harness 已就绪！${NC}"
echo "========================================="
echo "  底座后端:  http://localhost:8001"
echo "  运维中台:  http://localhost:81"
echo "  Prometheus: http://localhost:9090"
echo "  Grafana:    http://localhost:3000"
echo "========================================="
