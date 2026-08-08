# AI 编排服务（AI Orchestration Service）

基于 FastAPI 的独立 Agent Harness 编排服务，负责从 Django 单体中抽离 LangGraph 工作流编排能力。

## 职责边界

| 服务 | 职责 |
|------|------|
| **ai-orchestration-service** | Agent 编排、状态流转、进度推送、Plan/Verify |
| **Django backend** | 业务数据、测试用例、执行引擎、报告、用户认证 |

## 核心工作流

```
[Plan] → [Orchestrate] → [Verify]
   ↓          ↓              ↓
 LLM      HTTP 调用      LLM 验证
          Django API
```

## 本地运行

```bash
cd ai-orchestration-service
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
```

## Docker 运行

```bash
docker compose -f docker-compose.yml up -d
```

## API 入口

- 健康检查：`GET /api/v1/health`
- 同步工作流：`POST /api/v1/workflow/invoke`
- 流式工作流：`POST /api/v1/workflow/stream`
- 查询进度：`GET /api/v1/workflow/progress/{task_id}`
- 查询断点：`GET /api/v1/workflow/checkpoint/{task_id}`

## 断点续跑用法

1. 首次调用 `/stream` 时不传 `task_id`，服务返回 `X-Task-ID` 响应头。
2. 页面刷新或服务重启后，用同一个 `task_id` 重新调用 `/stream`，会从最新 checkpoint 继续执行。
3. 调用 `/checkpoint/{task_id}` 可查询当前 phase：`plan` / `orchestrate` / `verify` / `complete`。

```bash
# 首次调用
curl -N -X POST http://localhost:8001/api/v1/workflow/stream \
  -H "Content-Type: application/json" \
  -d '{"user_request":"生成登录接口测试用例"}'

# 断点续跑（替换为实际 task_id）
curl -N -X POST http://localhost:8001/api/v1/workflow/stream \
  -H "Content-Type: application/json" \
  -d '{"user_request":"生成登录接口测试用例","task_id":"abc123"}'
```

## 环境变量

| 变量 | 说明 |
|------|------|
| `DEEPSEEK_API_KEY` | DeepSeek API Key |
| `DASHSCOPE_API_KEY` | 通义千问 API Key |
| `GLM_API_KEY` | 智谱 API Key |
| `DJANGO_BASE_URL` | Django 业务服务地址，默认 `http://localhost:8000` |
| `REDIS_URL` | Redis 地址，用于状态持久化 |
