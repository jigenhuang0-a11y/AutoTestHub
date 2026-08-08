# Agent Harness

Agent Harness 是一个独立的 **AI 编排底座**，提供工作流编排、ReAct 智能体、MCP 工具网关、沙箱管控、团队隔离、链路追踪与监控等能力。

它与上层业务系统（如 AI 测试平台）通过标准 HTTP API 解耦，可被多个上层业务复用。

## 目录结构

```
agent-harness/
├── backend/              # FastAPI 编排引擎
│   ├── app/
│   │   ├── main.py
│   │   ├── api/v1/
│   │   ├── core/
│   │   └── ...
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/             # Vue 3 运维中台
│   ├── src/
│   │   ├── views/
│   │   ├── router/
│   │   ├── stores/
│   │   └── api/
│   ├── package.json
│   └── vite.config.js
├── monitoring/           # Prometheus + Grafana + OTel 配置
├── docker-compose.yml
└── README.md
```

## 本地开发

```bash
# 1. 启动底座后端
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload

# 2. 启动底座前端（新终端）
cd frontend
npm install
npm run dev
```

前端默认地址：http://localhost:5174  
后端默认地址：http://localhost:8001

## Docker 一键启动

```bash
# 复制环境变量模板
cp .env.example .env
# 编辑 .env 填入 LLM API Key 和 SERVICE_TOKEN

# 启动底座全部服务
docker-compose up -d
```

服务端口：

| 服务 | 端口 | 说明 |
|---|---|---|
| Orchestrator | 8001 | FastAPI 编排服务 |
| Harness 前端 | 81 | Nginx 托管的 Vue 应用 |
| Redis | 6380 | 底座状态缓存 |
| Prometheus | 9090 | 指标采集 |
| Grafana | 3000 | 监控面板 |
| OTel Collector | 4317/4318 | 链路数据收集 |

## 默认演示账号

```
admin       / admin123456
debug_user  / admin123456
```

> 2.12 阶段使用独立 demo 账号登录，后续会统一接入标准认证。

## API 概览

| 能力 | 端点 |
|---|---|
| 健康检查 | `GET /api/v1/health/live` |
| 工作流编排 | `POST /api/v1/workflows/run` |
| 任务列表 | `GET /api/v1/tasks/` |
| MCP 工具列表 | `GET /api/v1/tools/` |
| 工具调用 | `POST /api/v1/tools/call` |
| 记忆查询 | `GET /api/v1/memory/search` |
| 模板管理 | `GET /api/v1/templates/` |

