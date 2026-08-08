# 面试话术与项目亮点（Agent Harness 效能中台）

> 用途：面试「测试开发 / AI 应用开发 / 全栈」岗位时，针对本项目的技术原理、架构设计与场景设计问答准备。
> 配套：简历中本项目描述为「统一模型底座 + 自研 Loop Engine + 插件化 AI 业务层」。

---

## 一、一句话定位（电梯陈述）

> 我主导设计了一套 **Agent Harness 效能中台**：把分散的 AI 能力（模型调用、工具执行、Agent 编排、RAG、评测）收敛到一个统一底座，业务方以「插件」形式接入，获得统一的配额管控、安全护栏、全链路 Trace 与自动评测。核心调度内核是自研的有限状态机 Loop Engine，不依赖 LangChain/LangGraph。

---

## 二、为什么自研而不是用 LangChain/LangGraph？（高频题）

**错误答法**：「LangGraph 不好用 / 有 bug / 社区不成熟。」

**正确答法**（背这段）：
> 我非常认可 LangChain、LangGraph 在快速验证 AI 应用原型上的价值。但这个项目定位是面向 SaaS 的 Agent 效能中台，未来要支持多租户隔离、任务断点续跑、人工审核介入、统一计费与流量管控。LangGraph 的运行时由框架托管，原生很难深度定制任务生命周期；LangChain 抽象较重，难以实现全链路强制管控所有模型调用。基于它们开发，商业化需要的定制能力会产生大量补丁、积累技术债。所以我**吸收 Loop Engineering 的工程思想，自研 Loop Engine 作为调度内核**，同时保留 LangChain 里文本分割、文档加载等工具函数，做到不被框架绑定。

---

## 三、核心架构（五层，能画出来）

```
L5 前端管控层   Vue3 原型（工作台/配置中心/评测中心/监控大屏）
L4 业务场景层   用例生成 / RAG问答 / Multi-Agent / 性能测试 —— 全是「中台插件」
L3 调度内核层   Loop Engine（FSM）：PLAN→TOOL_CALL→OBSERVE→REFLECT→VERIFY→END，支持 PAUSE 人工介入/断点续跑
L2 能力支撑层   工具注册中心 + OpenClaw 沙箱（Docker隔离）+ 记忆 + Multi-Agent 编排者
L1 统一模型底座 多模型适配器(DeepSeek/通义) + 配额/限流/熔断 + 安全护栏 + 自动埋点
存储层         MySQL(元数据) + Redis(限流/队列) + Milvus(向量)
```

---

## 四、三条架构红线（体现架构定力）

1. **业务插件不得直连第三方模型/工具**，只能调中台原语 —— 否则无法统一管控、计费、审计。
2. **底座开发以「跑通一条业务链路」为终点**，不为抽象而抽象。
3. **任何新功能 = 新插件 or 内核增强**，禁止在业务代码写死调度逻辑。

---

## 五、Loop Engine 设计亮点（重点准备）

- **状态机显式可审计**：转移表 `TRANSITIONS` 集中定义，每个状态一个 handler，调度与业务解耦。
- **可持久化 checkpoint**：引擎快照可序列化，支持断点续跑（SaaS 长任务刚需）。
- **人工介入 PAUSE/RESUME**：REFLECT 判定需人工确认时挂起，外部 resume 从断点继续。
- **自我反思 REFLECT**：每轮 LLM 自评质量，不满意自动回退重做（最多限次防死循环）。
- **多分支守卫**：handler 返回 `Guard` 决策（continue/retry/satisfied/human）驱动转移，而非硬编码 while。

**面试追问「和 LangGraph 比差在哪」答**：LangGraph 的状态图也是图，但它的检查点、人工介入、子图隔离都要按其约定写，定制成本高；我的 FSM 转移表 + checkpoint 是我自己掌控的，断点续跑、人工审核流可以按中台需求自由组合，也更容易做全链路 Trace 与监控。

---

## 六、统一模型底座亮点

- **多模型适配器**：DeepSeek 主力、通义千问备用，统一 `chat()/embedding()` 接口，业务无感切换。
- **路由 + 降级**：主力失败自动切备用，配电路熔断器（连续失败打开）。
- **配额/限流/熔断**：按租户 QPS 令牌桶限流，保护下游。
- **安全护栏**：Prompt 注入检测 + 输出合规校验，护栏失败不中断业务而是结构化返回。
- **自动埋点**：每次调用全量记录 token/耗时/模型/状态，驱动评测与监控大屏。

---

## 七、场景设计题（准备 2-3 个）

**Q：如何保证生成的测试用例质量？**
A：双保险——(1) Loop Engine 内 REFLECT 让 LLM 自评覆盖度，不满意重做；(2) 独立的 LLM-as-Judge 评测服务按覆盖度/清晰度/可执行性三维打分，分数写入 Trace，监控大屏可看趋势。

**Q：多租户场景下如何隔离？**
A：底座按 `tenant_id` 维度做限流/配额/埋点隔离；L4 业务插件共享内核但记忆命名空间按 tenant/user 隔离；未来 MySQL 表加 tenant_id 行级隔离，沙箱按租户配资源配额。

**Q：Agent 执行出错/卡死怎么办？**
A：熔断器防雪崩；REFLECT 重试限次防死循环；VERIFY 校验不通过回退；极端情况 PAUSE 转人工介入，checkpoint 保证断点可恢复。

**Q：工具执行如何防恶意代码？**
A：工具注册中心按 `sandbox_required` 路由到 OpenClaw Docker 沙箱，容器限制 CPU/内存/超时且网络隔离；未启用 Docker 时本地降级兜底（仅开发用）。

---

## 八、项目数据（演示时可讲）

- 已落地 3 个业务插件：测试用例生成（单/多 Agent）、RAG 知识库问答。
- 端到端实测：单 Agent 用例生成含 REFLECT 重试完整跑通；Multi-Agent 编排 planner/generator/reviewer 协作；全链路 Trace 8+ Span；SSE 流式输出；监控指标实时聚合。
- 技术栈：Python 3.11 + FastAPI + SQLModel + MySQL + Redis + Milvus + Docker。
