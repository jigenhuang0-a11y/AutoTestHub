# AI 测试平台 - 架构文档

> 最后更新：2026-07-20
> **项目已统一**：Agent Harness（AI 编排底座）已纳入本仓库 `agent-harness/` 目录，两个项目统一版本管理。

---

## 项目定位

AI 测试平台 = **上层业务系统**，与 **Agent Harness 底座** 通过标准 HTTP API 解耦。

```
ai-test-platform/  （统一仓库）
│
├── agent-harness/                   ← AI 编排底座
│   ├── backend/  (FastAPI :8001)    ReAct/工作流/LLM路由
│   └── frontend/ (Vue 3 :5174)     运维中台UI
│
├── agent-harness/ (FastAPI :8001)   唯一自包含服务
├── frontend/     (Vue 3 :5173)      测试平台UI
│
├── docker-compose.yml               统一容器编排
└── start.bat                        一键本地启动
```

### 为什么从"大平层"拆成"两栋独栋别墅"

| | 拆分前（大平层） | 拆分后（同仓库，独立服务） |
|---|---|---|
| 仓库 | 1 个 monorepo 塞 4 套代码 | 1 个仓库，`agent-harness/` + `backend/` + `frontend/` 三套独立服务 |
| 部署边界 | 模糊，启动业务必须带底座 | 清晰，可分别部署、分别升级 |
| 复用性 | 底座与业务耦合，无法单独交付 | 底座可独立 SaaS 化 |
| 团队协同 | 一个仓库容易冲突 | 底座团队和平台团队各自独立发版 |
| 认证 | 统一 SERVICE_TOKEN | 各自可独立接入 OAuth2/OIDC |
| 消息/监控 | 统一 docker-compose | 统一 docker-compose，各自可独立接入 Kafka/Prometheus |

**核心思想不变**：工作流引擎、ReAct Agent、LLM 路由、多租户命名空间——这些底座逻辑仍然由 `agent-harness` 提供，只是从"内嵌"变成"独立服务"。

---

## 与 Agent Harness 底座的交互方式

上层业务系统调用底座能力的统一入口：

```
用户请求（测试用例生成 / 测评 / 数据工厂）
    │
    ▼
ai-test-platform/backend/       ── 业务校验、权限、数据准备
    │
    ▼ HTTP + SERVICE_TOKEN
agent-harness/backend/
    │
    ▼
Workflow Harness / ReAct Agent / LLM Router
    │
    ▼
ToolGateway / MCP 工具 / 记忆 / 沙箱
    │
    ▼
返回结果给业务平台
```

典型调用路径：

| 业务场景 | 业务平台入口 | 底座 API |
|---|---|---|
| AI 生成测试用例 | `POST /api/testcases/ai-generate/` | `POST /api/v1/workflows/run` |
| AI 测评任务 | `POST /api/ai-evaluator/run/` | `POST /api/v1/workflows/run` |
| 数据工厂生成 | `POST /api/data-factory/generate/` | `POST /api/v1/workflows/run` |
| 查看任务监控 | 跳转到底座前端 | `GET /api/v1/tasks/` |
| 链路日志 | 跳转到底座前端 | `GET /api/v1/traces/{task_id}` |

---

## 本项目（ai-test-platform）内部架构

### 核心组件

```
┌─────────────────────────────────────────────┐
│              FastAPI + Pydantic              │
│  ┌──────────────┐  ┌──────────────────────┐ │
│  │ accounts/    │  │ testcases/           │ │
│  │ 用户/角色/权限 │  │ 用例 CRUD/AI 生成     │ │
│  ├──────────────┤  ├──────────────────────┤ │
│  │ knowledge_/  │  │ execution/           │ │
│  │ 知识库/RAG   │  │ 测试执行/调度          │ │
│  ├──────────────┤  ├──────────────────────┤ │
│  │ ai_evaluator/│  │ data_factory/        │ │
│  │ AI 测评师    │  │ 数据工厂             │ │
│  ├──────────────┤  ├──────────────────────┤ │
│  │ quality_/    │  │ performance/         │ │
│  │ 质量数字人   │  │ 性能测试             │ │
│  ├──────────────┤  ├──────────────────────┤ │
│  │ agent_gateway/│  │ self_healing/        │ │
│  │ AI 工具 API  │  │ 自主纠错             │ │
│  └──────────────┘  └──────────────────────┘ │
└─────────────────────────────────────────────┘
```

### 数据流

```
用户请求（测试用例 / 测评 / 数据生成）
    │
    ▼
业务平台 backend 校验权限、准备上下文
    │
    ▼
调用 Agent Harness 底座 API（HTTP + SERVICE_TOKEN）
    │
    ▼
底座返回生成结果 / 执行结果 / 链路数据
    │
    ▼
业务平台持久化结果、生成报告、展示给用户
```

---

## 核心设计决策

### 1. 两套 Harness → 统一为独立底座

**背景**：项目早期同时存在两套 Agent Harness：
- `agent-harness/backend/app/core/workflow.py`（唯一 Agent Harness 大脑）
- 独立服务 `ai-orchestration-service/app/core/workflow.py`（现已迁移到 `agent-harness/backend/app/core/workflow.py`）

**决策**：彻底移除 Django。统一以 `agent-harness/backend` 为唯一自包含服务，所有工具（search/generator/data_factory/execution/evaluator）用 FastAPI 本地函数重写，由本地 ToolRegistry 管理，无跨服务 HTTP 调用。

**理由**：
- 为 SaaS 化铺路：平台提供通用业务，底座提供通用工作流原语，各团队可有自己的工作流模板
- 私有工具注册、独立记忆命名空间（team_id/user_id）、模型偏好
- 平台适配团队风格，而不是团队削足适履适配平台
- 物理隔离后，底座可以单独卖给其他团队/业务线使用

### 2. Django 职责剥离（已废弃：Django 已彻底移除）

| 原 Django 业务层职责 | 现状（已迁移到 Agent Harness 底座层） |
|------------------------|------------------------|
| RAG 知识库（CRUD、向量检索） | 用例生成策略/决策 |
| 用例管理、测试执行 | 评估流程编排 |
| AI 测评师、数据工厂 | ReAct 思考循环 |
| 用户/权限/角色 | 工作流引擎、checkpoint |
| 业务层 MCP 工具注册 | MCP 工具网关执行 |
| 测试报告/质量数字人 | 链路追踪、沙箱、团队隔离 |

### 3. 服务间认证设计

**问题（历史）**：早期编排服务调底座 workflow 时，缺少"用户登录 token"会导致 401。现已通过 JWT 中间件统一注入 `request.state.user` 解决。

**方案**：
- 两层认证：`X-Service-Token`（服务间）+ 用户 token fallback
- 编排服务的 `ToolGatewayClient` 自动注入服务 token
- Agent Harness 侧 JWT 中间件注入 `request.state.user`（含 role），`require_admin` 统一校验
- 工作流接收 `auth_token` 参数但不强制要求，自动兜底

### 4. 多租户预留

在 workflow 中预留 `team_id` 命名空间：
- 工具注册按 team 隔离
- 记忆/知识库按 team+user 命名空间
- LLM 模型选择支持按 team 偏好

---

## 已完成功能

- [x] Workflow Harness（Plan/Orchestrate/Verify/ReAct/Checkpoint）
- [x] ReAct Agent 思考循环
- [x] LLM Router（多模型选择 + fallback）
- [x] 本地 ToolRegistry 集成（Django MCP 已移除，改本地函数）
- [x] 服务间认证（X-Service-Token）
- [x] workflow.py `_resolve_auth_token()` 兜底逻辑
- [x] orchestrator Docker 健康检查修复
- [x] backend 代码挂载到容器（热更新）
- [x] **项目物理拆分：ai-test-platform 与 agent-harness 成为两个独立项目**
- [x] 业务平台前端移除 Harness 内嵌页面，目录结构整洁化

---

## 下一步

> **原则**：先做实底座，再跑业务链路。底座不稳，上层全是空中楼阁。

### 第二阶段：底座做实（当前）—— mock → 真实持久化，前后端联调
- [ ] 任务管理持久化（SQLite/Postgres）
- [ ] 租户管理持久化
- [ ] 沙箱管理持久化（从真实进程状态获取）
- [ ] MCP 工具注册持久化
- [ ] 模型/Prompt 配置持久化
- [ ] ReAct 接入真实 ToolGateway
- [ ] 前端 6 页面对接真实后端数据

### 第三阶段：业务链路跑稳
- [x] 用例生成端到端（workflow → LLM Router → 本地工具）
- [ ] 用例执行端到端（沙箱执行 → 结果回传）
- [ ] RAG 问答端到端（文档 → Milvus → 检索增强）
- [ ] 团队级记忆/工具/模型隔离验证

### 第四阶段：面试准备
- [ ] 项目亮点卡片、架构图
- [ ] 30 道自问自答
- [ ] 简历优化

### 第五阶段：上云（可选）
- [ ] 服务器恢复
- [ ] 远程部署验证

---

## 面试话术

> "这个项目的核心是一个 AI 编排底座。用 ReAct Agent 做思考循环，LLM Router 做多模型调度，MCP 协议做工具集成。早期为了快速验证，Django 内和独立服务各写了一套 Harness；后续统一成单一大脑，并且把这个大脑从业务平台里彻底拆出来，成为独立的 `agent-harness` 项目。`ai-test-platform` 只保留上层业务系统，两者通过标准 HTTP API 解耦。这样 SaaS 化时每个团队可以有自己的工作流模板、私有工具注册、独立记忆和模型偏好，底座还能单独交付给其他业务线使用。企业落地时各自上 K8s、接入统一认证网关即可，核心引擎逻辑和底座能力不用改。"
