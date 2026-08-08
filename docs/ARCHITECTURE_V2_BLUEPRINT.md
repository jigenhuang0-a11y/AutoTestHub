# AutoTestHub V2 架构蓝图：Agent 编排智能底座

> **目标**：基于 **LangChain + LangGraph + MCP** 构建 Agent 编排底座，
> 替换当前散乱的 LLM 调用，实现多 Agent 协作的全流程测试自动化。
> 同时引入 **Milvus** 替代 ChromaDB，支撑大规模向量检索。

---

## 一、现状诊断（痛点）

### 1.1 当前 AI 层架构

```
┌─────────────────────────────────────────────────────┐
│                   前端 (Vue3)                        │
└──────────┬──────────┬──────────┬──────────┬─────────┘
           │          │          │          │
    ┌──────▼──┐  ┌────▼────┐ ┌──▼──────┐ ┌▼────────┐
    │知识库问答│  │用例生成 │ │AI测评   │ │数据工厂 │
    │RAG      │  │         │ │         │ │         │
    └────┬────┘  └────┬────┘ └──┬──────┘ └┬────────┘
         │            │         │          │
    ┌────▼────────────▼─────────▼──────────▼──────┐
    │              core/llm_provider.py             │
    │  (DashScope / DeepSeek / GLM / SiliconFlow)  │
    │        ← 纯 API 封装，无编排能力               │
    └──────────────────────────────────────────────┘
         │                    │
    ┌────▼────┐         ┌────▼────────┐
    │ ChromaDB│         │ 直接 HTTP 调用│
    │(本地文件)│         │(各模块各自为战)│
    └─────────┘         └─────────────┘
```

### 1.2 核心问题

| # | 痛点 | 具体表现 |
|---|------|----------|
| 1 | **模型绑定死** | RAG 引擎硬编码千问，无法切换/路由不同模型 |
| 2 | **各模块割裂** | 知识库、测评、用例生成、数据工厂各自调 AI，没有统一入口 |
| 3 | **Chromadb 不够用** | 十万级以内，无法支撑企业级多用户并发场景 |
| 4 | **无 Agent 概念** | 只有"调一次 LLM"，没有"Agent 规划→执行→验证"的工作流 |
| 5 | **代码重复严重** | `llm_provider.py` 和 `services.py` 各自实现了 HTTP 调用逻辑 |

---

## 二、目标架构（V2）

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                        前端层 (Vue3 + Element Plus)                  │
│   Dashboard │ 测试用例 │ 套件管理 │ 执行历史 │ 知识库 │ 数据工厂 │ ... │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ REST API / SSE
┌──────────────────────────▼──────────────────────────────────────────┐
│                       API 网关层 (Django DRF)                        │
│     accounts │ testcases │ execution │ testsuites │ knowledge │ ...   │
│                              ↓                                      │
│                     ┌────────────────┐                               │
│                     │ Agent Gateway  │  ← 统一 AI 入口               │
│                     │ (新增 Django App) │                            │
│                     └───────┬────────┘                               │
└─────────────────────────────┼───────────────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────────────┐
│                      Agent 编排层 (LangGraph)                         │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    Harness Controller                        │    │
│  │   ┌─────────┐    ┌──────────────┐    ┌─────────────────┐   │    │
│  │   │  Plan   │───▶│ Orchestrate  │───▶│     Verify      │   │    │
│  │   │ Agent   │    │   (Routing)  │    │   (Validation)  │   │    │
│  │   └─────────┘    └──────┬───────┘    └─────────────────┘   │    │
│  │                          │                                   │    │
│  │                   ┌──────▼───────┐                          │    │
│  │                   │ State Mgmt   │                          │    │
│  │                   │ (共享状态)    │                          │    │
│  │                   └──────────────┘                          │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                     │
│  ┌───────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐  │
│  │ Analyzer  │ │Generator │ │Executor  │ │Evaluator │ │Data    │  │
│  │ 需求分析  │ │ 用例生成  │ │ 测试执行  │ │ 结果评估  │ │Factory │  │
│  │ Agent     │ │ Agent    │ │ Agent    │ │ Agent    │ │ Agent  │  │
│  └─────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └───┬────┘  │
│        │            │           │           │          │       │
└────────▼────────────▼───────────▼───────────▼──────────▼───────┘
         │            │           │           │          │
┌────────▼────────────▼───────────▼───────────▼──────────▼───────┐
│                      能力层 (LangChain)                          │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────────────┐    │
│  │ LLM Router  │  │ Embedding   │  │ Tool / MCP Protocol  │    │
│  │ (模型路由)   │  │ (向量化)    │  │ (工具/MCP协议扩展)   │    │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬───────────┘    │
│         │                │                     │                │
│  ┌──────▼────────────────▼─────────────────────▼───────────┐   │
│  │                 Model Provider Pool                      │   │
│  │  Qwen3(私有) │ DeepSeek │ GLM │ SiliconFlow │ Ollama   │   │
│  └─────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────▼────────────────────────────────────┐
│                      存储层                                       │
│  ┌────────────────┐  ┌───────────┐  ┌────────────────────────┐  │
│  │ Milvus 2.x     │  │ PostgreSQL│  │ Redis (缓存/任务队列)  │  │
│  │ 向量数据库      │  │ 业务数据  │  │ Session / Job Queue   │  │
│  │ (替代ChromaDB) │  │ 用户/权限 │  │ SSE 连接状态           │  │
│  └────────────────┘  └───────────┘  └────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

### 2.2 分层职责

#### Layer 1: Agent Gateway（API 入口）
- 新建 Django App：`agent_gateway`
- 所有 AI 相关请求统一经过这里
- 负责：鉴权、请求校验、异步任务分发（Celery）、SSE 推送
- 对外暴露 RESTful API，内部调用 LangGraph 工作流

#### Layer 2: Harness Controller（编排控制）
基于 **LangGraph State Machine** 实现：

```python
# 伪代码 - 核心概念
from langgraph.graph import StateGraph, END

class TestWorkflowState(TypedDict):
    # 输入
    user_request: str           # 用户原始需求
    context: dict               # 上下文（文档、历史等）
    
    # Plan 阶段输出
    plan: list[dict]            # 执行计划 [{step, agent, input}]
    
    # Orchestrate 阶段
    current_step: int           # 当前步骤索引
    agent_results: list[dict]   # 各 Agent 的执行结果
    
    # Verify 阶段
    verification: dict          # 验证结果 {passed, issues, score}
    
    # 最终输出
    final_output: dict

def build_test_workflow():
    workflow = StateGraph(TestWorkflowState)
    
    # 节点定义
    workflow.add_node("plan", PlanAgent())       # 分析需求，制定计划
    workflow.add_node("orchestrate", Router())   # 路由到具体 Agent
    workflow.add_node("verify", VerifyAgent())   # 验证结果质量
    
    # 边定义
    workflow.set_entry_point("plan")
    workflow.add_edge("plan", "orchestrate")
    workflow.add_conditional_edges(
        "orchestrate",
        should_continue,   # 还有未完成的 step?
        {"continue": "orchestrate", "done": "verify"}
    )
    workflow.add_conditional_edges(
        "verify",
        is_verified,       # 通过验证?
        {"retry_plan": "plan", "pass": END}
    )
    
    return workflow.compile()
```

#### Layer 3: 专业 Agent（执行单元）

| Agent | 职责 | 输入 → 输出 | 使用的工具 |
|-------|------|-------------|-----------|
| **PlanAgent** | 解析用户需求，拆解测试任务 | 需求描述 → 结构化执行计划 | LLM推理 + 知识库检索 |
| **TestCaseGenerator** | 从需求/API文档生成测试用例 | 需求/接口规范 → 用例列表 | LLM + Prompt模板库 |
| **DataFactoryAgent** | 构造测试数据 | 数据规则 → 测试数据集 | Faker + LLM增强 |
| **ExecutionAgent** | 执行测试用例 | 用例+数据 → 执行结果 | pytest引擎 + 断言器 |
| **EvaluatorAgent** | 评估测试结果/AI回答质量 | 结果/期望 → 评分报告 | 多维度评估框架 |
| **KnowledgeAgent** | RAG知识问答 | 问题 → 答案+引用 | Milvus检索 + LLM合成 |

#### Layer 4: 能力层（基础设施）

##### LLM Router（模型路由）
```
请求进来 → 判断任务类型 → 选择最优模型 → 调用 → 返回

路由策略:
- 复杂推理/规划     → Qwen-Max 或 DeepSeek-R1（强推理）
- 快速对话/SSE流式   → Qwen-Plus（性价比）
- 多模态(图片)       → Qwen-VL-Plus
- 代码生成/调试      → DeepSeek-Coder
- 简单分类/提取      → Qwen-Turbo（最快最便宜）
- 私有化部署        → Ollama 本地模型
```

##### MCP 协议扩展（未来）
```
MCP Server 可注册的工具:
- database_query: 查询业务数据库
- file_system: 读写测试文件
- git_operations: Git操作
- test_runner: 执行pytest
- browser_automation: Playwright操作
- notification: 发送通知
```

---

## 三、存储升级：ChromaDB → Milvus

### 3.1 选型理由

| 维度 | 当前 ChromaDB | 目标 Milvus 2.x |
|------|--------------|----------------|
| **数据量级** | 十万级（本地文件） | 亿~百亿级 |
| **并发能力** | 单进程锁 | 分布式高并发 |
| **部署方式** | 嵌入式（随Django启动） | 独立服务/Docker |
| **适合场景** | 开发、Demo | 大规模AI平台、私有化集群 |
| **过滤搜索** | 弱（metadata where） | 强（标量+向量混合过滤） |
| **多租户** | 手动 collection 隔离 | Partition Key 原生支持 |

### 3.2 迁移方案

```
阶段一（共存）：
  新知识库 → 写 Milvus
  旧知识库 → 保持 ChromaDB 只读，后台逐步迁移
  
阶段二（切换）：
  全部走 Milvus
  ChromaDB 配置保留作为降级方案
  
阶段三（清理）：
  移除 ChromaDB 依赖
  清理旧向量数据
```

### 3.3 Milvus 集成架构

```python
# backend/core/vector_store/milvus_store.py
from pymilvus import connections, Collection, FieldSchema, CollectionSchema, DataType, utility

class MilvusVectorStore:
    """Milvus 向量存储封装"""
    
    def __init__(self, collection_name: str):
        self.collection_name = collection_name
        self._ensure_collection()
    
    def _get_schema(self) -> CollectionSchema:
        fields = [
            FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=64),
            FieldSchema(name="kb_id", dtype=DataType.INT64),           # 知识库ID（分区键）
            FieldSchema(name="doc_id", dtype=DataType.INT64),            # 文档ID
            FieldSchema(name="chunk_index", dtype=DataType.INT64),       # 分块序号
            FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=8192),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=1024),  # text-embedding-v3
            FieldSchema(name="metadata", dtype=DataType.JSON),            # 扩展元数据
            FieldSchema(name="created_at", dtype=DataType.INT64),
        ]
        return CollectionSchema(fields, f"KB:{self.collection_name}")
    
    def search(self, query_vector: list, kb_id: int = None, top_k: int = 5) -> list:
        """混合检索：向量相似度 + 标量过滤"""
        expr = f"kb_id == {kb_id}" if kb_id else None
        results = self.collection.search(
            data=[query_vector],
            anns_field="embedding",
            param={"metric_type": "COSINE", "params": {"nprobe": 16}},
            limit=top_k,
            expr=expr,
            output_fields=["content", "metadata", "doc_id"]
        )
        return self._format_results(results)
```

---

## 四、目录结构规划

```
backend/
├── core/                          # 核心能力层（重构）
│   ├── __init__.py
│   ├── llm_provider.py            # [保留] 统一 LLM Provider
│   ├── config.py                  # [新增] AI 平台配置中心
│   │
│   ├── models/                    # [新增] 模型相关
│   │   ├── __init__.py
│   │   ├── router.py              # LLM Router（按任务类型选模型）
│   │   ├── provider_pool.py       # Provider 实例池（连接复用）
│   │   └── prompts/               # Prompt 模板库
│   │       ├── base.py            # 基础模板
│   │       ├── testcase_gen.py    # 用例生成模板
│   │       ├── evaluation.py      # 评估模板
│   │       ├── data_factory.py    # 数据构造模板
│   │       └── rag.py             # RAG 模板
│   │
│   ├── vector_store/              # [新增] 向量存储层
│   │   ├── __init__.py
│   │   ├── base.py                # 抽象基类
│   │   ├── milvus_store.py        # Milvus 实现（主力）
│   │   ├── chroma_fallback.py     # ChromaDB 降级备选
│   │   └── embeddings.py          # 统一 Embedding 接口
│   │
│   ├── tools/                     # [新增] Agent 工具集
│   │   ├── __init__.py
│   │   ├── base_tool.py           # 工具基类
│   │   ├── db_query.py            # 数据库查询工具
│   │   ├── file_ops.py            # 文件操作工具
│   │   ├── test_runner.py         # 测试执行工具
│   │   └── web_fetch.py           # 网页抓取工具
│   │
│   └── agents/                    # [新增] Agent 定义
│       ├── __init__.py
│       ├── base_agent.py          # Agent 抽象基类
│       ├── plan_agent.py          # 需求分析/规划 Agent
│       ├── generator_agent.py     # 用例/数据生成 Agent
│       ├── executor_agent.py      # 执行 Agent
│       ├── evaluator_agent.py     # 评估 Agent
│       ├── knowledge_agent.py     # 知识库 RAG Agent
│       └── harness/               # [新增] 编排引擎
│           ├── __init__.py
│           ├── state.py           # 共享状态定义
│           ├── workflow.py        # LangGraph 工作流构建
│           ├── router.py          # Agent 路由器
│           └── verifier.py        # 结果验证器
│
├── agent_gateway/                 # [新增] Agent 网关 App
│   ├── __init__.py
│   ├── apps.py
│   ├── urls.py
│   ├── views.py                   # Agent API 视图
│   ├── serializers.py
│   ├── tasks.py                   # Celery 异步任务
│   ├── services/
│   │   ├── __init__.py
│   │   ├── gateway_service.py     # 请求转发到 LangGraph
│   │   └── sse_manager.py         # SSE 连接管理
│   └── models.py
│
├── knowledge_base/                # [重构] 迁移至 Milvus
│   └── services.py                # RAGEngine → 改用 core/vector_store
│
├── ai_evaluator/                  # [重构] 改用 Agent
│   └── engine.py                  # AIEvaluatorEngine → EvaluatorAgent
│
├── data_factory/                  # [重构] 改用 Agent
│   └── views.py                   # generate_llm_dataset → DataFactoryAgent
│
└── testcases/                     # [重构] 改用 Agent
    └── services.py                # AITestCaseGenerator → GeneratorAgent
```

---

## 五、实施路线图

### Phase 1：地基搭建（预计 3-5 天）

**目标**：搭好 `core/` 层，不影响现有功能

- [ ] **1.1** 安装依赖：`langchain`, `langgraph`, `pymilvus`, `celery`, `redis`
- [ ] **1.2** 创建 `core/models/router.py` — LLM Router（从现有 `llm_provider.py` 升级）
- [ ] **1.3** 创建 `core/vector_store/milvus_store.py` — Milvus 封装
- [ ] **1.4** 创建 `core/config.py` — 统一配置（模型、向量库、MCP 等）
- [ ] **1.5** Docker Compose 新增 Milvus + Redis 服务
- [ ] **1.6** 创建 `agent_gateway/` App 骨架

### Phase 2：Agent 底座（预计 3-5 天）

**目标**：实现 Harness 编排模式，跑通第一个工作流

- [ ] **2.1** 实现 `base_agent.py` — Agent 基类（状态、工具、LLM 调用）
- [ ] **2.2** 实现 `harness/state.py` — 共享状态定义
- [ ] **2.3** 实现 `harness/workflow.py` — LangGraph 工作流（Plan → Route → Verify）
- [ ] **2.4** 实现 `plan_agent.py` — 第一个可工作的 Agent
- [ ] **2.5** 实现 `knowledge_agent.py` — 将现有 RAGEngine 重构为 Agent 形态
- [ ] **2.6** 端到端验证：前端发起请求 → Agent Gateway → LangGraph → 返回结果

### Phase 3：专业 Agent 逐一迁移（每个 1-2 天）

**目标**：将现有功能逐一迁移到 Agent 架构下

- [ ] **3.1** `generator_agent.py` — 替换 `AITestCaseGenerator` + `AIEvaluatorEngine._call_ai_generate`
- [ ] **3.2** `data_factory_agent.py` — 替换 DataFactory 中的 LLM 数据生成
- [ ] **3.3** `evaluator_agent.py` — 替换 `AIEvaluatorEngine` 主流程
- [ ] **3.4** `executor_agent.py` — 增强 `run_debug_execution`，加入 Agent 自主修复能力

### Phase 4：Milvus 迁移 + Dashboard 真实化（预计 2-3 天）

- [ ] **4.1** 新知识库写入 Milvus，旧数据后台迁移脚本
- [ ] **4.2** Dashboard KPI 接入真实统计查询
- [ ] **4.3** 清理 ChromaDB 依赖（保留 fallback）

### Phase 5：MCP + 高级特性（可选，面试加分项）

- [ ] **5.1** MCP Server 实现（database、file_system、test_runner 工具）
- [ ] **5.2** Agent 自主纠错循环（Verify 不通过 → 自动修复 → 重新执行）
- [ ] **5.3** 多 Agent 并行执行优化
- [ ] **5.4** 执行过程可视化（前端展示 Agent 工作流进度）

---

## 六、关键技术决策记录（ADR）

### ADR-001: 为什么选 LangGraph 而非 CrewAI/AutoGen？

| 维度 | LangGraph | CrewAI | AutoGen |
|------|-----------|--------|---------|
| 状态管理 | 内置 TypedDict State | 手动传递 | 消息驱动 |
| 流程可视化 | 内置 Graphviz | 无 | 有但复杂 |
| 与 LangChain 集成 | 原生 | 需适配 | 需适配 |
| 学习曲线 | 中 | 低 | 高 |
| 生产就绪度 | 高（LangChain官方） | 中 | 中 |
| **结论** | ✅ **选择** | | |

**决定**：使用 LangGraph 作为 Agent 编排核心，LangChain 作为 LLM/Tool 抽象层。

### ADR-002: 为什么选 Milvus 而非 pgvector/Qdrant？

- pgvector：已有 PG 但向量性能上限低，不适合亿级场景
- Qdrant：轻量优秀但生态和社区规模不如 Milvus
- Milvus：专为大规模 AI 设计，Partition 支持多租户，云原生部署成熟
- **决定**：Milvus 作为主力，ChromaDB 作为开发环境 fallback

### ADR-003: 同步 vs 异步执行

- 同步（当前）：简单但阻塞，长任务超时
- 异步（目标）：Celery + Redis 任务队列 + SSE 推送结果
- **决定**：所有 Agent 调用通过 Celery 异步执行，前端通过 SSE 接收流式进度

---

## 七、面试亮点提炼

这个架构设计在面试中可以讲的核心卖点：

1. **从单体到微服务的思维演进**：把散乱的 LLM 调用抽象成 Agent 编排底座
2. **LangGraph State Machine**：Plan → Route → Verify 的可控工作流，不是黑盒调 API
3. **模型路由策略**：根据任务复杂度和成本动态选择最优模型（省钱又高效）
4. **Milvus 向量数据库升级**：理解不同向量库的适用场景，能做技术选型决策
5. **MCP 协议扩展性**：预留工具接入点，体现架构前瞻性
6. **SSE + Celery 异步架构**：解决长任务的用户体验问题

---

## 八、下一步行动

**确认此蓝图后，立即开始 Phase 1 实施。**

建议从以下第一件事开始：
1. 先装好 Milvus Docker 服务，验证连通性
2. 创建 `core/models/router.py`，把现有的 `llm_provider.py` 包装进去
3. 创建 `agent_gateway/` App 骨架

你觉得这个蓝图怎么样？有没有需要调整的地方？
