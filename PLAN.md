# AI 测试平台项目计划（2026.7 - 9 月）

> 最后更新：2026-07-20 (Phase 2 完成，重新规划冲刺 40K+)
> 核心策略：**30K 当钩子价先进面试流程 → 8 月下旬正式开 40-48K → 9 月中旬兜底 30-35K**

---

## 时间线总览

```
7.20 ────── 7.27 ────── 8.03 ────── 8.10 ────── 8.17 ────── 9.05 ────── 9.15
  │          │           │           │           │           │           │
 Phase 2    Phase 3     Phase 4    Phase 5     开始投递   面试冲刺    兜底/入职
 底座做实   工程化升级   可观测+压测  演示+话术   40-48K     拿offer      回调30-35K
 (已完成)   Docker+拆分  Grafana+k6
```

### 投递节奏（新）

| 阶段 | 时间 | 策略 | 期望薪资 |
|---|---|---|---|
| 练手期 | 7月下旬-8月上旬 | 少量投递练面试手感，投匹配度一般的 | 写 30K |
| 冲刺期 | 8.17 起 | 主投 AI 平台/效能平台/全栈岗，期望改 40-48K | 40-48K |
| 兜底期 | 9.15 起 | 如果还没拿到满意 offer，回调预期 | 30-35K |

**关键原则**：30K 只是吸引面试的钩子价，不是最终成交价。技术面表现好，面试官会重新定价。但同一家公司面试中不能改口——不同阶段投不同公司。

---

## 架构决策：统一为单一大脑，面向 SaaS 的插件化设计

### 1. 两套 Harness 的处理方式

**决策**：不“打通两套”，而是**只保留 `ai-orchestration-service` 作为唯一 Agent Harness 大脑**，删除/迁移 Django 内旧 Harness。

| 旧架构 | 新架构 |
|--------|--------|
| Django 内也跑 LangGraph | Django 只暴露 Agent 工具 API |
| 独立编排服务调用 Django | 独立编排服务仍然是唯一大脑 |
| 两套状态/进度各写各 | 统一 State、Checkpoint、Memory、Metrics |

### 2. 企业架构 / SaaS 视角

- **一个编排平面（Control Plane）**：`ai-orchestration-service` 提供通用工作流原语（Plan / Orchestrate / Verify / ReAct / Checkpoint）。
- **可插拔的工具层（Tool Plane）**：Django 里的用例生成、执行、评估、数据工厂等作为工具注册到 MCP/ToolGateway。
- **团队级自定义（Tenant Layer）**：
  - 每个团队可选自己的工作流模板（`team_id → workflow_template`）
  - 每个团队可注册私有工具（`team_id → tool_registry`）
  - 每个团队有独立记忆命名空间（`team_id/user_id`）
  - 每个团队可选自己的模型偏好（DeepSeek / Qwen / 私有模型）

**核心原则**：平台提供“积木”，团队按自己风格拼；不是团队削足适履去适配平台。

### 3. 面试话术（记录备用）

> “早期项目里为了快速验证，Django 内和独立编排服务各写了一套 Harness。后续我把它统一成单一大脑，Django 只当工具层。这样设计是为了 SaaS 化：每个团队可以有自己的工作流模板、私有工具、独立记忆和模型偏好，平台去适配团队，而不是让团队适配平台。”

---

## 当前架构全景（2026-07-18 真实状态）

### 项目物理拓扑

```
ai-test-platform/
│
├── frontend/                        # Vue 3 + Vite + Element Plus
│   └── src/                         # SPA 前端，Nginx 静态托管
│
├── backend/                         # Django 4.2.7 ← 工具层 + 网关
│   ├── ai_test_platform/            # Django 配置（settings/urls/wsgi）
│   │
│   ├── 业务 App（12个）
│   │   ├── accounts/                # 用户认证 & Custom User Model
│   │   ├── testcases/               # API 测试用例 CRUD
│   │   ├── testsuites/              # 测试套件管理
│   │   ├── execution/               # 测试执行引擎（沙箱化 subprocess）
│   │   ├── web_testcases/           # Web 自动化（Playwright + AI）
│   │   ├── performance/             # 性能测试（Locust）
│   │   ├── reports/                 # 测试报告生成
│   │   ├── knowledge_base/          # RAG 知识库
│   │   ├── ai_evaluator/            # AI 测评师（用例质量评估）
│   │   ├── quality_checker/         # 质量数字人
│   │   ├── data_factory/            # 数据工厂
│   │   └── agent_gateway/           # Agent 网关（统一 AI 入口 + MCP HTTP API）
│   │
│   ├── core/                        # 核心基础设施（工具库，独立于 Django）
│   │   ├── config.py                # 统一配置中心（模型注册表 / LLM 路由 / 向量库）
│   │   ├── llm_provider.py          # 多 LLM Provider（DashScope / DeepSeek / GLM / SiliconFlow）
│   │   ├── permissions.py           # RBAC 权限
│   │   ├── middleware.py             # RequestID 全链路追踪
│   │   ├── agents/                  # Agent 层（LangChain + LangGraph）
│   │   │   ├── base_agent.py        # Agent 抽象基类
│   │   │   ├── plan_agent.py        # 需求分析 Agent
│   │   │   ├── testcase_gen_agent.py# 用例生成 Agent
│   │   │   ├── execution_agent.py   # 执行调度 Agent
│   │   │   ├── evaluator_agent.py   # AI 评估 Agent
│   │   │   ├── knowledge_agent.py   # RAG 检索 Agent
│   │   │   ├── data_factory_agent.py# 数据工厂 Agent
│   │   │   ├── harness/             # LangGraph 工作流（旧，逐步废弃 → 编排服务）
│   │   │   │   ├── workflow.py
│   │   │   │   └── state.py
│   │   │   └── self_healing/        # 自主纠错引擎
│   │   │       └── engine.py
│   │   ├── mcp/                     # MCP 协议层
│   │   │   ├── server.py            # MCP Server（SSE 端点）
│   │   │   ├── client.py            # MCP Client（工具发现与调用）
│   │   │   ├── tools_adapter.py     # Django Tool → MCP Tool 适配
│   │   │   └── transport.py         # SSE/Stdio 传输
│   │   ├── tool_gateway/            # 统一工具网关（30/30 测试通过）
│   │   │   ├── gateway.py           # ToolGateway 统一入口
│   │   │   ├── registry.py          # 工具注册表（team_id 隔离）
│   │   │   ├── permissions.py       # 团队级工具白名单
│   │   │   ├── audit.py             # 审计日志
│   │   │   └── tests.py             # 30 条测试
│   │   ├── memory/                  # 三层记忆系统（骨架）
│   │   │   ├── base.py              # MemoryEntry 数据结构
│   │   │   ├── short_term.py        # 短期记忆（token 窗口 + 自动摘要）
│   │   │   ├── long_term.py         # 长期记忆（Milvus 持久化，team_id 隔离）
│   │   │   ├── working.py           # 工作记忆（任务级临时状态）
│   │   │   ├── retrieval.py         # 混合检索（短期+长期+工作）
│   │   │   └── manager.py           # MemoryManager 总控制器
│   │   └── tools/                   # Agent 工具实现
│   │       ├── knowledge_search.py  # 知识库搜索
│   │       ├── testcase_storage.py  # 用例存储
│   │       ├── execution_storage.py # 执行结果存储
│   │       ├── evaluation_storage.py
│   │       └── ...
│   │
│   └── seed_model_configs.py        # 预置模型配置（DeepSeek 等 API Key）
│
├── ai-orchestration-service/        # FastAPI 独立编排服务 ← 唯一大脑
│   ├── app/
│   │   ├── main.py                  # FastAPI 入口
│   │   ├── api/                     # API 路由层
│   │   │   └── v1/
│   │   │       ├── tasks.py         # 任务 CRUD + 执行
│   │   │       ├── checkpoints.py   # 断点续跑 API
│   │   │       ├── templates.py     # 工作流模板管理
│   │   │       └── tools.py         # 工具发现代理
│   │   ├── core/
│   │   │   ├── workflow.py          # LangGraph StateGraph 核心（Plan→Orchestrate→Verify）
│   │   │   ├── state.py             # 工作流 State 定义 + Checkpoint 支持
│   │   │   ├── router.py            # LLMRouter（模型路由 + 多 Provider 切换）
│   │   │   ├── sandbox.py           # 子进程沙箱（6/6 测试通过）
│   │   │   ├── template_store.py    # 工作流模板注册表
│   │   │   ├── checkpoint_store.py  # Redis/Postgres Checkpoint 持久化
│   │   │   ├── tool_discovery.py    # 动态工具发现（替换硬编码 AGENT_REGISTRY）
│   │   │   └── react/               # ReAct 多轮思考循环（骨架）
│   │   │       ├── agent.py         # ReActAgent：think→act→observe
│   │   │       ├── graph.py         # LangGraph StateGraph 构建
│   │   │       ├── state.py         # ReActState 定义
│   │   │       ├── prompts.py       # System Prompt 模板
│   │   │       ├── memory_bridge.py # ReAct ↔ Memory 桥接
│   │   │       └── integration.py   # 接入现有 workflow.py
│   │   └── models/                  # 数据模型
│   │       ├── task.py              # Task 模型
│   │       └── template.py          # WorkflowTemplate 模型
│   └── tests/                       # 41+ 测试用例
│
├── docker-compose.yml               # 一键部署：9 个容器
│   ├── db        (PostgreSQL 16)    # 关系数据
│   ├── redis     (Redis 7)          # 缓存 + Checkpoint + Celery Broker
│   ├── etcd + minio                 # Milvus 依赖
│   ├── milvus    (v2.4)             # 向量数据库（知识库 + 长期记忆）
│   ├── backend   (Django :8000)     # 工具层 API
│   ├── ai-orchestrator (:8001)      # 编排大脑
│   ├── celery                       # 异步任务 Worker
│   └── frontend  (Nginx :80)        # 静态资源 + API 代理
│
└── PLAN.md                          # 本文档
```

### 分层架构图（逻辑视角）

```
┌─────────────────────────────────────────────────────────┐
│                    用户 / 前端 (Vue3)                      │
│                   :80 Nginx 静态托管                       │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP API
┌──────────────────────┴──────────────────────────────────┐
│                  📡 Agent Gateway (Django)                │
│         统一入口 · REST API · MCP HTTP 端点 · WebSocket    │
└──────┬────────────────────────────────────────┬──────────┘
       │                                        │
       ▼                                        ▼
┌──────────────────────┐          ┌──────────────────────────┐
│   🧠 编排服务 (FastAPI)│          │   🔧 工具层 (Django Apps)  │
│   :8001               │  ◄───►  │   工具注册 & 执行            │
│                       │  工具调用 │                          │
│  · LangGraph 工作流    │          │  · testcases (用例管理)     │
│  · Plan/Orch/Verify   │          │  · execution (沙箱执行)     │
│  · ReAct 思考循环      │          │  · web_testcases (Playwright)│
│  · 断点续跑 Checkpoint │          │  · performance (Locust)    │
│  · 工作流模板注册       │          │  · ai_evaluator (AI 评估)  │
│  · Memory 记忆管理     │          │  · knowledge_base (RAG)    │
│  · Sandbox 沙箱隔离    │          │  · data_factory (数据)     │
└──────┬───────────┬─────┘          └──────────────────────────┘
       │           │
       ▼           ▼
┌──────────┐ ┌──────────┐ ┌──────────┐
│PostgreSQL│ │  Redis   │ │  Milvus  │
│   :5432  │ │  :6379   │ │  :19530  │
│ 关系数据  │ │缓存/断点  │ │ 向量搜索  │
└──────────┘ └──────────┘ └──────────┘
```

### 核心基础设施状态矩阵

| 模块 | 路径 | 状态 | 测试 |
|------|------|------|------|
| MCP 协议层 | `backend/core/mcp/` | ✅ 可用 | 集成验证 |
| ToolGateway | `backend/core/tool_gateway/` | ✅ 可用 | 30/30 通过 |
| Sandbox 沙箱 | `ai-orch.../core/sandbox.py` | ✅ 可用 | 6/6 通过 |
| Checkpoint 断点 | `ai-orch.../core/checkpoint_store.py` | ✅ 可用 | 集成验证 |
| Template 注册 | `ai-orch.../core/template_store.py` | ✅ 可用 | 41/41 通过 |
| ToolDiscovery | `ai-orch.../core/tool_discovery.py` | ✅ 可用 | 动态替换硬编码 |
| LLMRouter | `ai-orch.../core/router.py` | ✅ 可用 | 多模型路由 |
| SelfHealing | `backend/core/agents/self_healing/` | ✅ 可用 | 端到端验证 |
| ReAct 循环 | `ai-orch.../core/react/` | 📦 骨架 | 待连 LLM |
| Memory 记忆 | `backend/core/memory/` | 📦 骨架 | 待连 Milvus |

### 关键数据流：一个 AI 任务的完整路径

```
用户请求 "测登录功能"
  │
  ▼
agent_gateway (Django)  ──接收请求──► 编排服务 (FastAPI)
                                          │
                            ┌─────────────┴─────────────┐
                            ▼                           ▼
                      Plan Node                   Template Store
                   "拆成 3 步"                 匹配 team 专属模板
                            │
                            ▼
                     Orchestrate Node
                   ┌────────┼────────┐
                   ▼        ▼        ▼
              "生成用例"  "执行"   "评估"
                   │        │        │
                   ▼        ▼        ▼
              ToolGateway ──────────────────► Django 工具 App
              (权限检查+审计)                   执行 & 返回结果
                   │
                   ▼
              Verify Node ── 结果汇总 ──► 返回前端
                   │
              Checkpoint Store (Redis/Postgres)
              "每一步都存档，崩了能续"
```

---

## 阶段安排

### Phase 1：7.18 - 7.20（统一大脑 + 技术债补齐 + 项目整理）✅ 已完成

目标：把项目真正变成一个可运行的 Agent Harness，架构上为 SaaS 留好扩展点，物理目录统一到工作区。

| # | 任务 | 状态 | 产出 | 验证方式 |
|---|------|------|------|----------|
| 1.1 | 统一两套 Harness | ✅ 完成 | `agent-harness` 为唯一大脑；Django 旧 Harness 标记废弃 | 本地单测通过 |
| 1.2 | 设计团队级工作流模板注册表 | ✅ 完成 | `template.py` + `template_store.py` + templates API | 41/41 测试通过 |
| 1.3 | LangGraph Checkpoint 断点续跑 | ✅ 完成 | Redis/Postgres 持久化 + resume/retry-step | kill 后重启可恢复 |
| 1.4 | 最小代码沙箱 | ✅ 完成 | FileJail + psutil 资源限制 + CodeSafetyChecker | 6/6 测试通过 |
| 1.5 | 自愈能力合并到主 Harness | ✅ 完成 | 失败重试 + 错误诊断 + 修复建议 | 端到端验证 |
| 1.6 | 项目物理整理（目录统一） | ✅ 完成 | agent-harness/ 纳入工作区，废弃目录删除 | start.bat 一键启动 5 服务 |
| 1.7 | Agent Harness 运维中台前端骨架 | ✅ 完成 | 8 页面 + 路由守卫 + 角色权限 + 暗色主题 | 浏览器可交互 |
| 1.8 | Agent Harness 后端 API 骨架 | ✅ 完成 | 12 模块 API 全部注册，管理 CRUD 用 mock 占位 | curl 可调通 |

**里程碑 1.0** ✅：底座骨架完整——核心引擎真实可用，管理 API + 前端页面骨架全部就位（但管理类数据为内存 mock）。

---

### Phase 2：7.20 - 7.27（底座做实：mock → 真实，前后端联调）✅ 已完成

目标：把底座的管理 API 从内存 mock 全部替换为真实持久化，前端对接真实数据流。

| # | 任务 | 状态 | 产出 | 验证方式 |
|---|------|------|------|----------|
| 2.1 | 任务管理持久化 | ✅ | SQLite 持久化，7 条种子 + stats 真实聚合 | pytest + curl |
| 2.2 | 租户管理持久化 | ✅ | tenants 表 + 3 条种子 + API Key 管理 | CRUD 全量验证 |
| 2.3 | 沙箱管理持久化 | ✅ | sandboxes 表 + 8 条种子 + execute 真实引擎 | 13/13 通过 |
| 2.4 | MCP 工具注册持久化 | ✅ | mcp_tools 表 + 6 条种子工具 | CRUD 验证 |
| 2.5 | 模型/Prompt 管理持久化 | ✅ | 版本号 + 热更新 | 改 Prompt → 重启 → 版本+1 |
| 2.6 | ReAct 接入真实 ToolGateway | ✅ | GatewayFactory 自动注入 | 6/6 冒烟测试 |
| 2.7 | 前端联调修复 | ✅ | 健康检查/网关开关/链路日志/租户工具白名单 | 29/29 集成测试 |
| 2.8 | 端到端验证 | — | 创建租户→注册工具→跑 ReAct→查看链路 | 待完成 |

**里程碑 2.0** ✅：底座可独立演示——核心 API 全部真实持久化，前端联调通过。

---

### Phase 3：7.21 - 7.27（补核心缺口：权限 + 产品完整度）🔄 当前阶段

目标：让项目看起来是"完整产品"而不是 demo。补齐权限管理、修复体验问题、一条命令启动。

| # | 任务 | 说明 | 验证方式 |
|---|------|------|----------|
| **3.1** | **权限管理模块（RBAC）** | 用户/角色/权限 CRUD，admin/tester/viewer 三级角色，菜单和按钮按角色显隐 | 管理员可增删改用户和角色 |
| **3.2** | **修复体验问题** | 空数据表格空状态、报错友好提示、刷新不丢登录态、审计大屏兜底 | 所有页面无报错 |
| **3.3** | **docker-compose 一键启动** | **9 个容器全部可一键拉起**：frontend + backend (Django) + ai-orchestrator (FastAPI) + celery + postgres + redis + etcd + minio + milvus | 别人 10 分钟跑起来 |

**里程碑 3.0**：项目具备"产品感"——权限管理完整、体验无 bug、任何面试官都能跑起来。

---

### Phase 4：7.28 - 8.03（工程化升级：服务拆分 + 分布式）

目标：把架构叙事落地成能看到的工程结构。**这步直接支撑 40K 报价。**

| # | 任务 | 说明 | 验证方式 |
|---|------|------|----------|
| **4.1** | **服务拆分 + 统一网关** | frontend / api-gateway(Nginx) / backend(Django) / orchestrator(FastAPI) / worker(Celery) / pg / redis / milvus，统一网关 `/api/*` → backend，`/orch/*` → orchestrator | 7+ 个独立服务，网关转发正确 |
| **4.2** | **配置标准化** | 区分 dev/prod 配置，密钥走环境变量，DB 迁移脚本自动化 | .env 不暴露敏感信息 |
| **4.3** | **AI 用例生成端到端链路** | 前端输入需求 → orchestrator 工作流 → LLM 生成 → 用例入库 → 前端展示 | 生成 10 条有效用例 |
| **4.4** | **用例执行端到端链路** | 用例进入沙箱 → 执行 → 结果回传 → 报告生成 | 完成一个完整测试套件 |
| **4.5** | **RAG 问答端到端链路** | 上传文档 → Milvus 向量化 → 提问 → 检索增强回答 | 知识库问答可复现 |

**里程碑 4.0**：分布式微服务架构落地——7+ 个独立服务、3 条核心业务链路走通。

---

### Phase 5：8.04 - 8.10（可观测性 + 压测）

目标：让面试官相信架构能扛事。**有 QPS 数据的项目和没有的是两种项目。**

| # | 任务 | 说明 | 验证方式 |
|---|------|------|----------|
| **5.1** | **结构化日志 + 全链路追踪** | 所有服务输出 JSON 日志，统一 trace_id 跨服务串联，每个服务暴露 `/health` | 一个请求的日志能串起来 |
| **5.2** | **Prometheus + Grafana 监控** | QPS/延迟/错误率/LLM 调用耗时面板，告警规则 | 可视化仪表盘截图 |
| **5.3** | **k6/locust 压测** | 压核心 API（生成用例/执行任务/工具调用），拿到 QPS/P50/P99/P99.9 数据 | 压测报告，能找到瓶颈 |
| **5.4** | **瓶颈分析与优化记录** | 数据库连接池/LLM 调用延迟/沙箱超时 → 优化方案 | 有数据、有分析、有优化 |

**里程碑 5.0**：Production-ready 级别的可观测性——有监控、有压测报告、能讲出瓶颈和优化路线。

---

### Phase 6：8.11 - 8.17（演示材料 + 面试准备）

目标：把工程能力翻译成面试官能听懂的故事。

| # | 任务 | 产出 |
|---|------|------|
| **6.1** | **项目介绍 PDF** | 架构图 + 技术栈 + 核心模块 + 未来规划，1 页纸能讲清楚 |
| **6.2** | **演示视频/GIF** | 登录→创建租户→注册工具→AI 生成用例→沙箱执行→看报告，3 分钟内 |
| **6.3** | **面试话术 FAQ** | 30 秒版本 + 3 分钟版本，覆盖：项目介绍/架构设计/为什么拆分/AI 准确率/空窗期/学历 |
| **6.4** | **简历升级** | 职位标题改为「AI 平台全栈开发 / 效能平台工程师」，期望薪资改 40-48K |

**里程碑 6.0**：面试武器库就绪——能演示、能讲、能扛深问。

---

## 项目物理拓扑（当前）

```
agent-harness/
├── frontend/     (Vue 3 :5174)        运维中台 UI（8 页面）
├── backend/      (FastAPI :8001)      编排大脑（ReAct/工作流/沙箱/MCP/租户/审计）
│
ai-test-platform/
├── frontend/     (Vue 3 :5173)        测试平台 UI
├── backend/      (Django :8000)       工具层（用例/执行/RAG/数据工厂/性能测试）
│
docker-compose.yml
├── postgres  :5432
├── redis     :6379
├── etcd + minio + milvus :19530
├── django    :8000
├── orchestrator :8001
├── celery
└── nginx     :80
```

### API 边界

| 能力 | 服务 | 端点 |
|---|---|---|
| 工作流编排 | orchestrator (FastAPI) | `POST /api/v1/workflows/run` |
| 任务/租户/沙箱/审计/MCP | orchestrator (FastAPI) | `/api/v1/agent/*` `/api/v1/mcp/*` |
| 测试用例/执行/报告/RAG | backend (Django) | 平台自有 API |
| ReAct + 记忆 + 断点续跑 | orchestrator (FastAPI) | 编排大脑内部

---

## 薪资策略与市场定位

### 岗位定位（关键：别说自己是"测试"）

| 投递方向 | JD 关键词 | 定位叙事 |
|---|---|---|
| AI 平台开发 | Agent/编排/LLM/MCP/RAG | "Agent 编排中台，通用 AI 调度底座" |
| 效能平台工程师 | 效能平台/测试架构/质量工具 | "从 0 搭建 AI 驱动的效能平台，覆盖用例生成→执行→评估全链路" |
| 全栈/AI 应用工程师 | Python/FastAPI/Vue/Docker | "AI 工程化落地：多模型兼容 + 分布式编排 + 多租户 SaaS 架构" |

### 薪资谈判策略

| 谈判场景 | 话术 |
|---|---|
| HR 初筛问期望 | "30K 左右，具体看岗位的职责范围和平台建设空间" |
| 技术面后谈薪资 | "我这边不只看执行层面的工作，而是希望参与 AI 底座和效能平台的架构建设。基于通用调度、多模型兼容、SaaS 化架构的经验，期望在 35K 以上" |
| 被压价到 JD 范围 | "我理解 JD 写的范围，但如果更多是偏执行层面的工作，可能和我目前的能力方向不太匹配" |
| 最终 counter offer | "综合技术深度、平台落地经验和当前市场行情，我的期望是 40K 左右" |

### 真实市场定价参考（深圳 2026，自研中小厂）

| 能力层 | 薪资区间 | 你的情况 |
|---|---|---|
| AI 测试平台开发（执行层） | 18-25K | 外包三年无此项目 ≈ 这个档 |
| AI 效能平台开发（设计层） | 28-35K | 项目讲清楚 ≈ 这个档 |
| AI 平台架构（架构层） | 35-50K | 分布式+监控+压测做完 ≈ 这个档 |

**当前目标**：用 Phase 4-6 把项目推到"架构层"水准，支撑 40K+ 报价。

---

---

# ⚠️ 重大架构决策更新（2026-08-08）：彻底去 Django 化，重构为 Agent Harness 中台

> 原 PLAN.md 上半部分（Phase 1-6）基于旧架构（Django 工具层 + FastAPI 编排服务 + LangGraph）。
> 2026-08-08 起，项目方向升级为**彻底方案**：完全废弃 Django / Postgres / Celery / LangGraph，
> 全栈后端统一到 **FastAPI + SQLModel + MySQL + Redis + Milvus**，自研 Loop Engine 作为调度内核。
> 旧 Django 代码保留但标记 deprecated，不删除、不改造、不投入精力。

## 一、为什么选彻底方案（商业化视角）

- **双后端并存是烂尾之源**：Django + FastAPI 各管一半，改功能要两头动，跨栈 bug 难查。
- **框架绑死是迭代死穴**：LangGraph 深度嵌入后，加"人工介入/断点续跑"等商业化刚需时改不动。
- **模型调用散落无法管控**：计费、审计、多模型切换要全仓库搜 `openai.ChatCompletion`，收不完。
- 彻底方案把这三处**一次性收敛到中台内核**，未来新功能都是"挂插件"，迭代只增不改底座。

## 二、目标架构（五层，瘦身后）

```
L5 前端管控层     Vue3 原型（工作台/配置中心/评测中心/监控大屏）—— 复用现有 frontend/
L4 业务场景层     用例生成 / 问答评测 / RAG问答 / 性能测试 / 数字人 —— 全部是"中台插件"
L3 调度内核层     Loop Engine（FSM）：状态机 / 分支 / 反思 / 暂停恢复 / 重试熔断
L2 能力支撑层     工具注册中心 + OpenClaw 沙箱（Docker隔离） + 记忆/Memory + MCP网关
L1 统一模型底座   多模型适配器(DeepSeek/通义) + 配额/限流/熔断 + 安全护栏 + 自动埋点
    存储层        MySQL(业务/元数据) + Redis(缓存/限流/队列) + Milvus(向量)
```

**关键差异（比原方案更彻底）**：L4 业务层被强制定义为"插件"，每个业务是独立 Python 包，
通过注册装饰器挂载到中台，共享同一套 Loop Engine / 模型网关 / 沙箱。旧 Django 测试业务 = 一个插件。

## 三、仓库策略

- 在 `d:/AI_Project/ai-test-platform` 下新建：
  - `harness-core/`：新的 FastAPI 中台内核（config / logging / models / plugins / 未来 api/core）
  - `harness-plugins/`：业务插件目录（testcase_gen 等）
- 原有 `backend/`(Django) 保留，标记 deprecated，不删不改。
- 前端 `frontend/` 保留复用，仅改变数据接入层指向新中台。

## 四、三条架构红线（防烂尾铁律，写进 README）

1. **业务插件不得直连第三方模型/工具**，只能调中台原语。违例即架构违规。
2. **底座开发以"跑通一条业务链路"为终点**，不准为抽象而抽象。P1 用例生成能演示，底座就停手。
3. **任何新功能 = 新插件 or 内核增强**，禁止在业务代码里写死调度逻辑。

## 五、4 周阶段执行计划（8.08 启动）

| 阶段 | 时间 | 核心交付 | 红线 |
|------|------|----------|------|
| **P0 拆骨** | 8.08-8.10 | FastAPI 工程骨架 + Docker Compose 三件套 + SQLModel + 统一环境配置 | 禁止提前写 Agent 调度逻辑 |
| **P1 底座** | 8.11-8.14 | 打通第一条端到端链路：L1 多模型适配器(限流/熔断/埋点) + Loop Engine 最简 MVP + 工具注册中心 + 测试用例生成插件可完整演示 | 底座以跑通链路为终点 |
| **P2 增强** | 8.15-8.21 | OpenClaw 基础沙箱 + Loop Engine 增强(REFLECT/分支/人机介入/checkpoint) + RAG 插件 + 全链路 Trace + LLM 评测 + 插件抽象层 | 沙箱 P2 才实装 |
| **P3 收口** | 8.22-8.28 | 监控大屏(埋点驱动) + 可选迁移少量旧业务作插件示例 + 项目文档/架构图/压测/容错演练 + 简历物料 + 面试话术 | 永远优先保障可演示链路 |

## 六、P0 拆骨阶段任务清单（进行中）

| # | 任务 | 状态 | 产出 |
|---|------|------|------|
| P0.1 | FastAPI 工程骨架 | ✅ | `harness-core/harness_core/main.py` 健康检查可跑 |
| P0.2 | 统一配置中心 | ✅ | `config.py` 全环境变量集中管理 |
| P0.3 | 结构化日志 + trace_id | ✅ | `logging.py` |
| P0.4 | SQLModel 基础模型 | ✅ | tenants / agent_configs / call_logs / tool_registrations |
| P0.5 | 插件抽象接口 | ✅ | `plugins/__init__.py` 基类 + 注册表 |
| P0.6 | 第一个插件占位 | ✅ | `harness-plugins/testcase_gen/` |
| P0.7 | Docker Compose 三件套 | ✅ | mysql + redis + milvus(+etcd/minio) |
| P0.8 | 环境模板与依赖 | ✅ | `.env.example` + `requirements.txt` + `pyproject.toml` |
| P0.9 | README + 红线固化 | 🔄 | 本文档 + 仓库 README |

## 七、商业化演进路径

```
现在(8月)   彻底中台骨架 + 1条演示链路（用例生成）
   ↓
9-10月      接 RAG / 评测 / 数字人 等 3-5 个插件，形成产品矩阵
   ↓
年底        多租户隔离 + 配额计费，开始对外试商用
   ↓
明年        SaaS 化：团队可注册自己的模板/工具/记忆/模型偏好
```

---

## 风险与应对

| 风险 | 影响 | 应对 |
|---|---|---|
| 二本无学位证 | 大厂简历关过不去 | 主攻中小厂/创业公司，技术面能压过去 |
| 三年外包履历 | 面试官质疑深度 | 用项目架构叙事翻盘——外包写用例 vs 个人搭平台是两种人 |
| 半年空窗期 | HR 必问 | "系统学习 AI 工程化，并从 0 搭建了 Agent 编排中台" |
| 项目未上线 | 缺乏 production 验证 | Phase 5 做压测+监控弥补，强调"核心模块已本地验证" |
| 独立开发无协作 | 团队经验存疑 | 面试讲清楚"架构设计决策"和"接口边界设计"，体现协作思维 |

---

## 关键提醒

- **岗位定位决定薪资**：你是"AI 平台架构师"不是"测试工程师"，面试全程把这个叙事焊死。
- **30K 是钩子价**：先进面试流程，技术面表现好再向上谈，别在 HR 关就亮底牌。
- **Phase 4 服务拆分 + Phase 5 压测是 40K 的支点**：没有这两个，架构叙事空中楼阁。
- **每个能力必须有可见验证**：测试通过/监控截图/压测报告/演示视频，不能只是代码写完。
- **同一家公司不要改口**：练手期写 30K 的公司就按 30K 走到底；冲刺期新投的公司直接写 40-48K。
- **9 月 15 号硬底线**：如果还没 35K+ offer，立刻降预期到 28-35K 先入职。
- **🚨 绝不把核心编排源码推到公开仓库**：面试讲原理、展示效果，但源码私藏。
