# AI 编排服务 API 契约

版本: v1.0
服务: ai-orchestration-service
端口: 8001

---

## 1. 健康检查

### GET /api/v1/health/

返回服务状态和可用模型。

**响应：**
```json
{
  "status": "ok",
  "service": "ai-orchestration-service",
  "available_providers": ["deepseek", "dashscope"],
  "available_models": [
    {"name": "deepseek-chat", "provider": "deepseek", "capabilities": ["reasoning"], "priority": 3}
  ]
}
```

---

## 2. 同步工作流

### POST /api/v1/workflow/invoke

执行完整 Agent 工作流，同步返回结果。

**请求体：**
```json
{
  "user_request": "帮我测试订单系统的创建订单接口",
  "user_id": 1,
  "auth_token": "jwt-access-token"
}
```

**响应：**
```json
{
  "task_id": "a1b2c3d4",
  "status": "completed",
  "plan": [
    {"agent": "generator", "description": "生成测试用例"},
    {"agent": "execution", "description": "执行测试"}
  ],
  "results": [
    {"agent": "generator", "status": "completed", "result": {...}}
  ],
  "verification": {"passed": true, "score": 0.95, "summary": "满足需求"}
}
```

---

## 3. 流式工作流

### POST /api/v1/workflow/stream

SSE 流式执行工作流，实时推送每个步骤进度。

**请求体：**
```json
{
  "user_request": "帮我测试订单系统的创建订单接口",
  "user_id": 1,
  "auth_token": "jwt-access-token"
}
```

**SSE 事件类型：**
- `plan_start` / `plan_complete`
- `step_start` / `step_complete` / `step_failed`
- `verify_start` / `verify_complete`
- `workflow_complete`
- `error`
- `final_result`

---

## 4. 查询进度

### GET /api/v1/workflow/progress/{task_id}

查询任务当前进度。

**响应：**
```json
{
  "exists": true,
  "progress": {
    "total_steps": 3,
    "completed_steps": 2,
    "current_phase": "orchestrate",
    "steps": [...]
  }
}
```

---

## 5. 与 Django 的集成关系

```
前端 -> POST /api/agent/tasks/workflow_stream/  (Django)
          -> 转发到 POST /api/v1/workflow/stream  (编排服务)
            -> 编排服务生成 Plan
            -> 编排服务 HTTP 调用 Django /api/agent/tasks/{action}/
            -> 编排服务 Verify
            -> SSE 流原路返回给前端
```

Django 负责：认证、任务记录、ChatMessage 历史、业务 Agent 执行。
编排服务负责：Plan、Orchestrate、Verify、SSE 进度推送。

---

## 6. 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DEEPSEEK_API_KEY` | DeepSeek API Key | - |
| `DASHSCOPE_API_KEY` | 通义千问 API Key | - |
| `GLM_API_KEY` | 智谱 API Key | - |
| `DJANGO_BASE_URL` | Django 服务地址 | http://localhost:8000 |
| `REDIS_URL` | Redis 地址 | redis://localhost:6379/0 |
