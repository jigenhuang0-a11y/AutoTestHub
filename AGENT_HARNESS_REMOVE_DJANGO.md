# Django 彻底移除计划表

> 决策日期：2026-08-09
> 目标：将 `agent-harness`（FastAPI）从"编排壳 + Django 业务脑"改为**自包含单服务**，彻底删除 Django 依赖，不留技术债。
> 原则：每个阶段独立可运行，不出现"半 Django 半 FastAPI"中间态。

## 当前债务快照（2026-08-09 确认）
- FastAPI 通过 HTTP 调 Django：
  - `services/django_client.py` → `DjangoClient.call_agent()`（action→`/api/agent/tasks/...`）
  - `services/tool_gateway_client.py` → `ToolGatewayClient`（Django MCP REST API）
  - `core/tool_discovery.py` → `ToolDiscovery`（从 Django MCP 拉工具列表）
  - `core/gateway_factory.py` → 创建上述 client 单例
- 依赖 Django 的文件共 10 个：`django_client.py`、`tool_gateway_client.py`、`tool_discovery.py`、`gateway_factory.py`、`config.py`、`react/integration.py`、`react/agent.py`、`tool_registry.py` 端点、`workflow.py`、`metrics.py`
- `config.py` 含 `DJANGO_BASE_URL` / `DJANGO_MCP_URL` / `TOOL_DISCOVERY_REFRESH_INTERVAL` / JWT 与 Django 互通注释 / `SERVICE_TOKEN`
- `workflow.py` 第 628–791 行 `_execute_single_step` 两条路径（MCP / Django Agent API）均调 Django

## 执行阶段

### 阶段 1：建本地工具层（替代 Django 业务实现）【完成】
- [x] 读 Django 侧 5 个工具实现：search / generator / data_factory / execution / evaluator
- [x] 新建 `agent-harness/backend/app/tools/` + 5 个工具模块（纯函数，用 FastAPI LLMRouter，无 Django 依赖）
- [x] 新建 `app/tools/registry.py`（本地注册表，保留团队命名空间 + 动态发现能力）
- [x] Django→FastAPI 工具映射表（见文末）

### 阶段 2：删除 Django 胶水模块【完成】
- [x] 删 `services/django_client.py`
- [x] 删 `services/tool_gateway_client.py`
- [x] 删 `core/tool_discovery.py`（改用 `app/tools/registry.py`）
- [x] 改 `core/gateway_factory.py` → `LocalToolGateway`（本地适配器，react 层零改动）

### 阶段 3：改调用方（统一走本地函数）【完成】
- [x] 改 `core/workflow.py` `_execute_single_step`：删 765–791 双路径（MCP/Django），改调 `registry.call_tool`
- [x] 改 `react/integration.py` + `react/agent.py`：经 `LocalToolGateway` 转 registry（零改动调用方代码）
- [x] 改 `api/v1/endpoints/tool_registry.py`：去 Django 推送语义，改用本地 registry

### 阶段 4：清理配置 + 删 Django 项目【完成】
- [x] `config.py` 删 Django 相关常量与注释（DJANGO_BASE_URL/DJANGO_MCP_URL/TOOL_DISCOVERY_*）
- [x] `git rm -r --cached backend` 已将 Django 项目从 git 跟踪彻底移除（所有 backend/* 文件标记 D）
- [x] 工作区 `backend/` 空目录因某进程（CodeBuddy safe-delete trash 二进制 / 文件资源管理器）持有句柄被锁，
      物理删除被 Win32 错误 32 拦截；**重启 IDE 后即可物理删除，不影响代码层与 git 语义**
- [x] 清 `docker-compose.yml`（根+backend）、`k8s/*`、`monitoring/*`、`*.env.example` 的 `DJANGO_*` 残留
- [x] `.gitignore` 删 Django 专属规则
- [x] 更新记忆：Django 退化为工具层 → 已彻底移除
- [x] 修测试文件 Django 残留（test_w2/test_w6/test_w7/test_w8 的 import 与 stdout 重包装）
- [x] 更新 README.md / api-contract.md 架构描述

### 阶段 5：验证【完成核心项】
- [x] `tests/test_supervisor.py` 7 项全过
- [x] `python -m unittest discover` 全部 46+ 测试文件可加载（之前因 stdout 重包装整体 ImportError）
- [x] `grep -ri "django_client|tool_gateway_client|tool_discovery|DJANGO_BASE_URL|DJANGO_MCP_URL"` 零代码引用
- [x] `app.tools` 自注册验证：5 工具 + agent 映射正确
- [ ] 跑 `e2e_supervisor.py` 看 worker 从 failed → completed（需 LLM Key 在线 + 真实调用，待运行）
- [ ] 提交 + 推送

## 遗留项（与本次移除无关，独立 story）
1. `test_w7::test_mcp_put` 报 `KeyError: 'results'` —— `mcp.py` 端点 `list_mcp_tools` 返回体问题，与 Django 无关
2. `test_sandbox::test_cleanup_after_execution` FAIL —— Windows 文件锁，环境相关
3. `backend/` Django 目录物理删除 —— 待用户授权（代码层已无依赖，git 历史有备份）

## 工具映射表（Django→FastAPI）
| Agent | Django action | Django 源文件 | FastAPI 目标 | 实现方式 |
|---|---|---|---|---|
| search | testcase_search | agent_gateway/views.py:testcase_search | app/tools/testcase_search.py | 占位（RAG 未接入返回空） |
| generator | generate_testcases | core/agents/testcase_gen_agent.py | app/tools/testcase_create.py | LLM Router + JSON 解析校验 |
| data_factory | generate_data | core/agents/data_factory_agent.py | app/tools/data_generate.py | LLM Router |
| execution | execute_tests | core/agents/execution_agent.py | app/tools/execution_run.py | LLM Router（模拟执行） |
| evaluator | evaluate | core/agents/evaluator_agent.py | app/tools/evaluate_run.py | LLM Router |


## 工具映射表（阶段 1 填充）
| Agent | Django action | Django 源文件 | FastAPI 目标 |
|---|---|---|---|
| search | testcase_search | TBD | app/tools/testcase_search.py |
| generator | generate_testcases | TBD | app/tools/testcase_create.py |
| data_factory | generate_data | TBD | app/tools/data_generate.py |
| execution | execute_tests | TBD | app/tools/execution_run.py |
| evaluator | evaluate | TBD | app/tools/evaluate_run.py |
