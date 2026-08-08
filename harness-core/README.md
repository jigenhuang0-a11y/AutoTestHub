# Agent Harness Core（中台内核）

> 项目唯一后端大脑。彻底替代 Django + LangGraph。
> 所有 Agent 行为跑在自研 Loop Engine 上，所有模型调用走统一底座。

## 架构定位

```
L5 前端管控层 (复用 frontend/ Vue3)
L4 业务场景层 (harness-plugins/ 插件)
L3 调度内核层 (Loop Engine FSM)        ← 自研，P1 起
L2 能力支撑层 (工具注册 + 沙箱 + 记忆)  ← P2 起
L1 统一模型底座 (多模型适配 + 配额/限流/熔断 + 护栏 + 埋点)
存储: MySQL + Redis + Milvus
```

## 三条架构红线（不可逾越）

1. **业务插件不得直连第三方模型/工具**，只能调中台原语。
2. **底座开发以"跑通一条业务链路"为终点**，不为抽象而抽象。
3. **任何新功能 = 新插件 or 内核增强**，禁止在业务代码写死调度逻辑。

## 目录结构

```
harness-core/
├── harness_core/
│   ├── main.py          # FastAPI 入口（P0: 健康检查 + 启动自检）
│   ├── config.py        # 统一配置中心（环境变量）
│   ├── logging.py       # 结构化日志 + trace_id
│   ├── models/          # SQLModel: tenants / agent_configs / call_logs / tool_registrations
│   └── plugins/         # 插件抽象基类 + 注册表
├── harness_plugins/     # 业务插件（独立于内核，可单独部署）
│   └── testcase_gen/    # 用例生成插件（P1 实装）
├── docker-compose.yml   # MySQL + Redis + Milvus 三件套
├── requirements.txt
├── pyproject.toml
└── .env.example
```

## 快速启动

```bash
cd harness-core
python -m venv .venv && source .venv/Scripts/activate   # Windows
pip install -r requirements.txt
cp .env.example .env          # 填入 DEEPSEEK_API_KEY 等
uvicorn harness_core.main:app --reload --port 8001
# 健康检查: http://127.0.0.1:8001/health
# API 文档:  http://127.0.0.1:8001/docs
```

## 启动依赖（容器）

```bash
docker compose up -d mysql redis milvus
```

## 阶段计划

| 阶段 | 时间 | 交付 |
|------|------|------|
| P0 拆骨 | 8.08-8.10 | 本骨架 |
| P1 底座 | 8.11-8.14 | 多模型底座 + Loop Engine MVP + 用例生成端到端 |
| P2 增强 | 8.15-8.21 | 沙箱 + Loop 增强 + RAG + 评测 + 插件抽象层 |
| P3 收口 | 8.22-8.28 | 监控大屏 + 简历物料 + 压测 |
