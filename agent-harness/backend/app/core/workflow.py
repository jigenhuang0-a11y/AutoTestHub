"""
LangGraph 工作流构建器

编排服务版本：Plan -> Orchestrate -> Verify
- Plan: 本地 LLM 生成执行计划
- Orchestrate: HTTP 调用 Django 下游 Agent API
- Verify: 本地 LLM 验证结果
"""
import json
import logging
import os
import time
import uuid
import queue as queue_module
import threading
from typing import Literal
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.core.state import ProgressEvent, WorkflowProgress
from app.core.router import get_llm_router
from app.core.config import (
    DJANGO_BASE_URL, DJANGO_MCP_URL, AgentConfig, sandbox_config,
)
from app.core.telemetry import get_tracer
from app.core.checkpoint import (
    save_checkpoint, load_checkpoint, cleanup_checkpoint,
    record_step_retry, MAX_GLOBAL_RETRIES, MAX_STEP_RETRIES,
)
from app.core.metrics import (
    workflow_total,
    workflow_step_duration_seconds,
    workflow_active,
    llm_requests_total,
    llm_request_duration_seconds,
)
from app.core.template_store import get_template_sync
from app.core.robustness import (
    retry_with_backoff,
    RetryExhausted,
    call_with_robustness,
    call_llm_with_fallback,
    get_idempotency_tracker,
    get_circuit_breaker,
)
from app.core.audit_store import get_audit_store

logger = logging.getLogger(__name__)
tracer = get_tracer(__name__)

# 全局工作流配置（可从环境变量覆盖）
AGENT_CONFIG = AgentConfig()

# ============================================================
# Agent 注册表 — 版本 2.0：MCP 动态发现优先，硬编码回退
# ============================================================

# 回退用：硬编码的 Agent→Django action 映射
FALLBACK_AGENT_REGISTRY = {
    "search": "testcase_search",
    "generator": "generate_testcases",
    "data_factory": "generate_data",
    "execution": "execute_tests",
    "evaluator": "evaluate",
}

# 使用全局单例（与 tool_registry 端点共享同一 ToolDiscovery 实例）


def _get_tool_discovery():
    """获取全局 ToolDiscovery 单例"""
    from app.core.tool_discovery import get_global_discovery
    return get_global_discovery()


def resolve_agent_action(agent_name: str, team_id: str = None, auth_token: str = None) -> str:
    """
    解析 Agent 名为对应的 API action（MCP 优先，硬编码回退）
    
    Args:
        agent_name: Agent 名（如 "generator"）
        team_id: 团队 ID
        auth_token: Django 认证 Token（请求级透传）
        
    Returns:
        action 名称（如 "generate_testcases"）或 MCP tool 名
    """
    discovery = _get_tool_discovery()
    
    # 尝试从 MCP 工具列表解析
    if discovery.is_stale():
        discovery.refresh(team_id=team_id, auth_token=auth_token)
    
    # 当 Agent 是 generator 时，优先使用 Django Agent API generate_testcases，
    # 因为该接口已内建 LLM 生成 + 数据库保存，能解决 MCP 工具 testcase_create 参数不完整的痛点。
    if agent_name == "generator":
        return "generate_testcases"

    # data_factory 同样优先使用 Django Agent API generate_data，
    # 该接口支持 dataset_name / business_domain 等完整参数，避免 MCP 数据工厂 schema 缺失。
    if agent_name == "data_factory":
        return "generate_data"

    # search 直接使用 MCP 工具 testcase_search，无需走 Django Agent API
    if agent_name == "search":
        return "testcase_search"

    tool_name = discovery.resolve_agent(agent_name)

    if tool_name:
        logger.debug(f"[ToolDiscovery] {agent_name} → {tool_name}")
        return tool_name
    
    # 回退到硬编码
    action = FALLBACK_AGENT_REGISTRY.get(agent_name)
    if action:
        logger.debug(f"[ToolDiscovery.Fallback] {agent_name} → {action}")
        return action
    
    raise ValueError(f"未知 Agent: {agent_name}")


def _infer_data_factory_params(prompt: str, params: dict) -> dict:
    """从 prompt 和已有 params 推断数据工厂参数，避免数据集未命名。

    支持根据关键词推断业务域：
    - 登录/用户/注册/账号 -> user
    - 订单/商品/支付 -> order
    - 物流/快递/配送 -> logistics
    - 售后/退款/退货 -> after_sales
    """
    normalized = dict(params) if params else {}

    # 业务域：优先使用已有 domain / business_domain
    domain = normalized.get("business_domain") or normalized.get("domain", "")
    if not domain:
        text = prompt.lower()
        if any(k in text for k in ["订单", "商品", "支付", "价格", "purchase", "order"]):
            domain = "order"
        elif any(k in text for k in ["物流", "快递", "配送", "发货", "shipping", "logistics"]):
            domain = "logistics"
        elif any(k in text for k in ["售后", "退款", "退货", "客服", "after_sales"]):
            domain = "after_sales"
        elif any(k in text for k in ["登录", "注册", "用户", "账号", "user", "login", "auth"]):
            domain = "user"
        else:
            domain = "custom"

    normalized["business_domain"] = domain
    normalized.pop("domain", None)

    # 数据集名称：基于 prompt 生成，避免空字符串导致默认"未命名数据集"
    dataset_name = normalized.get("dataset_name", "")
    if not dataset_name:
        clean = prompt.strip()
        # 移除常见前缀，保留核心语义
        for prefix in ["生成", "创建", "帮我", "请", "为"]:
            if clean.startswith(prefix):
                clean = clean[len(prefix):].strip()
        dataset_name = f"AI生成-{clean[:30] or domain}-数据"
    normalized["dataset_name"] = dataset_name

    # 记录数量兜底
    if "record_count" not in normalized:
        normalized["record_count"] = 20

    # 策略兜底
    if "strategy" not in normalized:
        normalized["strategy"] = "smart"

    return normalized




def _extract_search_keyword(user_request: str) -> str:
    """从用户请求中提取搜索关键词。"""
    text = user_request or ""
    # 去除常见前缀和符号
    for prefix in ["帮我搜索", "搜索", "查找", "列出", "看看", "有哪些", "帮我找", "请"]:
        text = text.replace(prefix, "")
    # 去除“相关的测试用例”等后缀，保留核心名词
    for suffix in ["相关的测试用例", "相关测试用例", "测试用例", "用例", "相关"]:
        if text.endswith(suffix):
            text = text[: -len(suffix)]
    return text.strip() or user_request


PLAN_SYSTEM_PROMPT = """你是 AutoTestHub 的 Agent Harness 规划专家。请根据用户需求，拆解为可执行的 Agent 步骤。

可用 Agent：
- search: 从已有测试用例库中搜索/检索相关测试用例（用户说“搜索、查找、列出、看看、有哪些、帮我找”时用）
- generator: 生成新的测试用例（用户说“生成、创建、写、设计”时用）
- data_factory: 生成测试数据
- execution: 执行测试套件
- evaluator: 评估执行结果

意图判断规则（必须遵守）：
1. 如果用户请求包含“搜索、查找、列出、看看、有哪些、帮我找”，则计划数组中只包含 search Agent 步骤，不要包含 generator、data_factory、execution、evaluator。
2. 如果用户请求包含“生成、创建、写、设计”，则使用 generator，并视情况补充 data_factory、execution、evaluator 形成完整工作流。
3. 每个步骤的 prompt 必须保留用户的原始关键词，不要改写为“用户需求”或“用户请求”。
4. search 的 params.query 必须是用户原始请求中的具体关键词（如“登录”、“订单”），不要写成“用户需求”。

输出要求：
1. 只输出 JSON 数组，不要 Markdown 代码块
2. 每个步骤包含：agent, prompt, description, params(可选), parallel_group(可选), react(可选)
3. params 是传给下游 Agent API 的结构化参数
4. 如果两个步骤可以并行，给它们相同的 parallel_group
5. 对于 generator/evaluator，应添加 "react": true，启用 ReAct 推理循环（思考→工具调用→观察→决策）

示例 1（搜索类需求）：
[
  {"agent": "search", "prompt": "搜索登录相关的测试用例", "description": "搜索登录测试用例", "params": {"query": "登录", "limit": 20}}
]

示例 2（生成类需求）：
[
  {"agent": "generator", "prompt": "生成登录接口测试用例", "description": "生成测试用例", "params": {"requirement": "生成登录接口测试用例", "case_count": 5}, "react": true, "parallel_group": "A"},
  {"agent": "data_factory", "prompt": "生成登录测试数据", "description": "生成测试数据", "params": {"business_domain": "user", "record_count": 10}, "parallel_group": "A"},
  {"agent": "execution", "prompt": "执行生成的测试用例", "description": "执行测试", "params": {"test_case_ids": []}, "parallel_group": "B"},
  {"agent": "evaluator", "prompt": "评估执行结果", "description": "评估结果", "params": {"execution_id": 1}, "react": true, "parallel_group": "C"}
]
"""

# 模板填充 Prompt：在已有模板骨架的基础上，让 LLM 根据用户需求填充每个步骤的 prompt 和 params
TEMPLATE_FILL_PROMPT = """你是 AutoTestHub 的 Agent Harness 规划专家。

你有以下预定义的工作流模板骨架：
{template_skeleton}

请根据用户需求，填充这个模板中每步骤的 prompt 和 params：
1. prompt 字段：必须保留用户原始关键词，将用户需求具体化为该步骤的执行指令
2. params 字段：根据 step 的 params_schema 生成结构化的参数（key 对应 schema 中的类型，value 根据用户需求推断）

如果用户请求包含“搜索、查找、列出、看看、有哪些、帮我找”，应当优先填充 search 相关步骤，而不是直接生成新用例。

用户需求：{user_request}

输出要求：只输出 JSON 数组，不要 Markdown 代码块。每个元素对应模板中的一个步骤，包含：
- agent（继承模板）
- prompt（根据用户需求填充，保留原始关键词，不要写“未指定需求”）
- description（简短描述该步骤做什么）
- params（结构化参数，key 与 params_schema 一致）
- parallel_group（继承模板）
- step_index（继承模板的 order）

示例输出：
[
  {{"agent": "search", "prompt": "搜索登录相关的测试用例", "description": "搜索登录测试用例", "params": {{"query": "登录", "limit": 20}}, "parallel_group": "A", "step_index": 0}},
  ...
]
"""


VERIFY_SYSTEM_PROMPT = """你是 AutoTestHub 的 Agent Harness 验证专家。请根据用户原始需求和工作流执行结果，判断是否满足需求。

判断规则：
1. 如果用户要求搜索/查找/列出：只要返回了相关结果即算满足，不必执行和评估。
2. 如果用户要求生成：需要检查是否生成了符合要求的测试用例，且用例没有明显虚构不存在的接口。
3. 如果包含执行步骤：需要检查执行结果中的通过率和失败原因。
4. 如果没有任何步骤执行成功，说明计划失败，passed 应为 false。

输出要求：只返回 JSON 对象，不要 Markdown 代码块：
{"passed": true, "score": 0.95, "issues": [], "summary": "简要总结"}
"""


def _parse_plan(response_text: str) -> list:
    """解析 LLM 返回的执行计划"""
    text = response_text.strip()
    # 尝试去除 markdown 代码块
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.lower().startswith("json"):
            text = text[4:].strip()
    try:
        plan = json.loads(text)
        if isinstance(plan, list):
            return plan
        if isinstance(plan, dict) and "plan" in plan:
            return plan["plan"]
    except json.JSONDecodeError:
        logger.warning(f"[Plan] JSON 解析失败，尝试正则提取: {text[:200]}")
        import re
        match = re.search(r"\[.*?\]", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    return []


# MCP 工具名集合（通过 ToolGateway 调用的工具，而非 Django Agent API）
MCP_TOOL_PREFIXES = (
    "testcase_", "execution_", "data_", "knowledge_",
    "report_", "evaluate_", "system_",
)


def _is_mcp_tool(action: str) -> bool:
    """判断一个 action 是 MCP 工具还是 Django Agent API"""
    # 如果以已知 MCP 工具前缀开头，走 MCP 路径
    if action.startswith(MCP_TOOL_PREFIXES):
        return True
    # Django Agent API 的 action 名（generate_testcases, generate_data, execute_tests, evaluate）
    return False


def _mcp_result_to_dict(result: dict) -> dict:
    """将 MCP 返回结果转为 DjangoClient 兼容的 dict 格式"""
    try:
        content = result.get("content", [{"text": "{}"}])
        text = content[0].get("text", "{}")
        import json
        data = json.loads(text)
        if isinstance(data, dict):
            return data
        return {"data": data, "status": "success"}
    except (json.JSONDecodeError, IndexError, TypeError):
        return {"data": result, "status": "success"}


def _emit(state: dict, event_type: str, data: dict):
    """发送进度事件"""
    callback = state.get("progress_callback")
    task_id = state.get("task_id")
    if callback:
        try:
            callback(event_type, data)
        except Exception:
            pass
    if task_id:
        try:
            WorkflowProgress.update(task_id, event_type, **{
                k: v for k, v in data.items()
                if k in ["step_index", "status", "result", "error", "log"]
            })
        except Exception:
            pass


def _plan_from_template(template, user_request: str, team_id: str) -> list:
    """基于模板骨架 + LLM 填充参数生成执行计划"""
    # 构建模板骨架描述
    skeleton_lines = [f"模板名称：{template.name}"]
    skeleton_lines.append(f"偏好模型：{template.model_preference}")
    skeleton_lines.append("步骤骨架：")
    for s in template.steps:
        schema_desc = ", ".join(
            f"{k}({v.get('type', 'string')})" for k, v in s.params_schema.items()
        ) if s.params_schema else "无参数"
        skeleton_lines.append(
            f"  order={s.order} agent={s.agent} "
            f"prompt_template=\"{s.prompt_template}\" "
            f"params_schema={{{schema_desc}}} "
            f"parallel_group={s.parallel_group or '无'}"
        )
    skeleton_text = "\n".join(skeleton_lines)

    prompt = TEMPLATE_FILL_PROMPT.format(
        template_skeleton=skeleton_text,
        user_request=user_request,
    )

    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": f"请按模板填充执行计划：{user_request}"},
    ]

    router = get_llm_router()
    llm_start = time.time()
    response = call_llm_with_fallback(
        router, messages, task_type="planning", fallback_model="deepseek-chat", team_id=team_id
    )
    llm_request_duration_seconds.labels(provider="auto", model="auto").observe(time.time() - llm_start)
    steps = _parse_plan(response)

    if not steps:
        # LLM 填充失败，直接用模板骨架生成回退计划
        logger.warning(f"[Harness.Plan] 模板填充失败，使用裸模板骨架")
        steps = [
            {
                "agent": s.agent,
                "prompt": s.prompt_template.format(user_request=user_request),
                "description": f"{s.agent}: {s.prompt_template[:40]}",
                "params": {},
                "parallel_group": s.parallel_group,
                "step_index": s.order,
            }
            for s in template.steps
        ]

    for i, s in enumerate(steps):
        if "step_index" not in s:
            s["step_index"] = i

    return steps


def plan_node(state: dict) -> dict:
    """Plan 节点：优先使用团队模板生成执行计划，无模板时回退 LLM 自由生成"""
    user_request = state.get("user_request", "")
    if not user_request:
        return {"plan": [], "errors": ["用户请求为空"]}

    task_id = state.get("task_id")
    team_id = state.get("team_id", "default")
    template_id_arg = state.get("template_id")

    _emit(state, ProgressEvent.PLAN_START, {"task_id": task_id, "request": user_request[:200]})
    logger.info(f"[Harness.Plan] 接收需求: {user_request[:100]}... team={team_id}")

    # ── 审计：工作流启动 ──
    try:
        audit = get_audit_store()
        audit.write_workflow_event(
            task_id=task_id or f"wf-{uuid.uuid4().hex[:8]}",
            user_id=str(state.get("user_id", "system")),
            team_id=team_id,
            stage="plan",
            status="start",
            message=f"工作流启动: {user_request[:100]}",
        )
    except Exception:
        pass  # 审计记录失败不影响工作流

    # ---- 模板感知逻辑 ----
    template = get_template_sync(team_id, template_id_arg)
    steps_via_template = False

    try:
        if template and template.status.value == "published":
            logger.info(
                f"[Harness.Plan] 使用模板: {template.template_id} "
                f"'{template.name}' v{template.version} ({len(template.steps)} 步骤)"
            )
            with tracer.start_as_current_span("harness.plan.template") as span:
                span.set_attribute("task_id", task_id)
                span.set_attribute("template_id", template.template_id)
                span.set_attribute("team_id", team_id)
                steps = _plan_from_template(template, user_request, team_id)
            steps_via_template = True
        else:
            # 无模板：回退到 LLM 自由生成（向后兼容）
            logger.info(f"[Harness.Plan] team={team_id} 无已发布模板，使用 LLM 自由生成")
            router = get_llm_router()
            messages = [
                {"role": "system", "content": PLAN_SYSTEM_PROMPT},
                {"role": "user", "content": f"用户需求：{user_request}\n\n请生成执行计划，只输出 JSON 数组。"},
            ]
            with tracer.start_as_current_span("harness.plan.free") as span:
                span.set_attribute("task_id", task_id)
                llm_start = time.time()
                response = call_llm_with_fallback(
                    router, messages, task_type="planning", fallback_model="deepseek-chat", team_id=team_id
                )
                llm_duration = time.time() - llm_start
                llm_requests_total.labels(provider="auto", model="auto", status="success").inc()
                llm_request_duration_seconds.labels(provider="auto", model="auto").observe(llm_duration)
            steps = _parse_plan(response)

        if not steps:
            raise ValueError("LLM 未返回有效计划")

        for i, s in enumerate(steps):
            s["step_index"] = i

        if task_id:
            WorkflowProgress.register(task_id, steps)

        _emit(state, ProgressEvent.PLAN_COMPLETE, {
            "task_id": task_id,
            "steps": [{"agent": s["agent"], "description": s.get("description", "")} for s in steps],
            "via_template": steps_via_template,
        })

        reasoning = f"模板 '{template.name}'" if (template and steps_via_template) else "LLM 生成"
        result = {
            "plan": steps,
            "plan_reasoning": reasoning,
            "current_step": 0,
            "context": state.get("context", {}),
            "team_id": team_id,
            **_passthrough_state(state),
        }
        save_checkpoint({**state, **result}, phase="plan")
        return result

    except Exception as e:
        logger.warning(f"[Harness.Plan] 计划生成失败，使用回退计划: {e}")
        fallback_plan = [
            {"step": 1, "agent": "generator", "prompt": user_request, "description": "生成测试用例", "step_index": 0},
        ]
        if task_id:
            WorkflowProgress.register(task_id, fallback_plan)
        result = {
            "plan": fallback_plan,
            "plan_reasoning": "回退计划",
            "current_step": 0,
            "context": state.get("context", {}),
            "team_id": team_id,
            **_passthrough_state(state),
        }
        save_checkpoint({**state, **result}, phase="plan")
        return result


# LangGraph StateGraph(dict) 不会自动保留未列出的 key，
# 每个节点必须显式透传这些关键状态字段
_PASSTHROUGH_KEYS = ["auth_token", "user_request", "task_id", "user_id", "template_id", "team_id"]


def _passthrough_state(state: dict) -> dict:
    """从 state 中提取必须透传的字段"""
    return {k: state.get(k) for k in _PASSTHROUGH_KEYS}


# ============================================================
# ReAct 集成 — Agent 使用 ReAct 推理循环执行复杂任务
# ============================================================

# 默认启用 ReAct 的 Agent（这些 Agent 的任务需要多步推理 + 工具调用）
REACT_CAPABLE_AGENTS = frozenset({"generator", "evaluator"})


def _exec_react_step(
    agent_name: str,
    params: dict,
    prompt: str,
    step: dict,
    state: dict,
) -> dict:
    """
    使用 ReActAgent 执行单步（替代传统 _call_agent）。

    当 step 标记 react=True 或 agent 在 REACT_CAPABLE_AGENTS 中时，
    用 ReAct 思考-行动-观察循环替代一次性 API 调用。

    Returns:
        dict 兼容 _call_agent 格式: {"status": "success", "response": ..., "react_trace": {...}}
    """
    from app.core.gateway_factory import get_react_integration

    auth_token = state.get("auth_token") or os.getenv("SERVICE_TOKEN")
    team_id = state.get("team_id", "default")

    logger.info(
        f"[Harness.ReAct] 步骤使用 ReAct 执行 "
        f"agent={agent_name} prompt={prompt[:60]}..."
    )

    integration = get_react_integration(
        auth_token=auth_token,
        team_id=team_id,
    )

    result = integration.execute_step_with_react(
        step=step,
        state=state,
    )

    if result.get("status") == "success":
        trace = result.get("react_trace", {})
        logger.info(
            f"[Harness.ReAct] 完成 "
            f"iterations={trace.get('iterations')} "
            f"decision={trace.get('decision')}"
        )
        return {
            "status": "success",
            "response": result["data"].get("response", ""),
            "react_trace": trace,
        }

    # ReAct 失败：返回错误信息
    error_msg = result.get("data", {}).get("response", "ReAct 执行异常")
    logger.error(f"[Harness.ReAct] 失败: {error_msg}")
    raise ValueError(error_msg)


# ── 输出审计：对单步执行结果做安全兜底（脱敏/拦截） ──
_step_output_guard = None


def _get_step_output_guard():
    global _step_output_guard
    if _step_output_guard is None:
        from app.core.security import OutputGuard
        from app.core.config import security_config
        _step_output_guard = OutputGuard(block_critical=security_config.output_block_critical)
    return _step_output_guard


def _audit_step_output(result: dict) -> dict:
    """
    单步执行结果兜底审计：
    - 扫描 response / sandbox stdout 等字段的敏感信息（API Key、内网 IP）
    - 命中 critical → 脱敏为 [REDACTED]，保留结果可用性
    - 命中 critical 且策略要求阻断 → 标记 audit_blocked
    """
    from app.core.config import security_config
    if not security_config.output_guard_enabled or not isinstance(result, dict):
        return result
    try:
        raw = json.dumps(result, ensure_ascii=False, default=str)
    except Exception:
        return result
    scan = _get_step_output_guard().scan(raw)
    if not scan.violations:
        return result
    logger.warning(
        f"[Security] 单步输出审计命中 | agent 上下文 | violations={scan.violations}"
    )
    # 无论是否阻断，先脱敏（绝不把明文密钥/内网地址透传给上游）
    clean_result = result
    try:
        clean_result = json.loads(scan.cleaned_text)
    except Exception:
        pass
    if not scan.is_safe:
        # 策略要求阻断：脱敏后追加审计标记（内容已打码，非明文）
        clean_result = dict(clean_result)
        clean_result["audit_blocked"] = True
        clean_result["audit_warning"] = f"OUTPUT_BLOCKED: {scan.violations}"
    return clean_result


def _execute_single_step(step: dict, state: dict) -> dict:
    """执行单步：调用 Django 下游 Agent API（含自愈）"""
    from app.services.django_client import DjangoClient
    from app.core.self_healing import SelfHealingEngine, ErrorClassifier, ErrorCategory

    agent_name = step.get("agent", "unknown")
    prompt = step.get("prompt", "")
    step_index = step.get("step_index", 0)
    start = time.time()

    task_id = state.get("task_id")
    auth_token = state.get("auth_token") or os.getenv("SERVICE_TOKEN")
    if not auth_token:
        logger.warning(f"[Harness] _execute_single_step: auth_token MISSING — Django MCP 调用将 401")

    _emit(state, ProgressEvent.STEP_START, {
        "task_id": task_id, "step_index": step_index,
        "agent": agent_name, "description": step.get("description", ""),
    })

    params = step.get("params") or {}
    if agent_name == "data_factory":
        params = _infer_data_factory_params(prompt, params)
    if agent_name == "search":
        # search 必须提供 query；如果 LLM 没生成或生成为通用词，从用户请求提取关键词兜底
        if not params.get("query") or params.get("query") in ("用户需求", "用户请求", "需求"):
            user_request = state.get("user_request", "") or prompt
            params["query"] = _extract_search_keyword(user_request)
        if "limit" not in params:
            params["limit"] = 20
    if agent_name == "generator":
        # generator 的 requirement 必须包含完整需求，不能只写关键词
        if not params.get("requirement") or len(str(params.get("requirement"))) < len(str(prompt)) / 2:
            params["requirement"] = prompt
    if "prompt" not in params:
        params["prompt"] = prompt

    def _execute_via_sandbox(agent_name: str, p: dict) -> dict:
        """
        通过底座沙箱执行代码类任务（execution / 带 code 的 generator）。
        仅在 sandbox_config.enabled 时调用；任何沙箱异常都会回退到 Django Agent API
        并在审计日志中告警，绝不让代码在底座进程内裸跑。
        """
        from app.core.sandbox import SandboxExecutor, SandboxConfig, SandboxStatus

        cfg = sandbox_config
        sbox_cfg = SandboxConfig(
            timeout_seconds=cfg.default_timeout_seconds,
            max_memory_mb=cfg.default_max_memory_mb,
            max_processes=cfg.default_max_processes,
            # 安全策略：默认拒绝网络，仅放行白名单主机
            allow_network=cfg.allow_network,
            allowed_hosts=cfg.allowed_hosts,
            allowed_write_paths=cfg.allowed_write_paths,
            read_only_paths=cfg.read_only_paths,
            env_whitelist=cfg.env_whitelist or None,
            injected_env=cfg.injected_env or {},
        )
        executor = SandboxExecutor(sbox_cfg)

        # 优先执行 p["code"]（Agent 生成的脚本）；否则回退执行用例文件
        if p.get("code"):
            logger.info(f"[Harness.Sandbox] 在沙箱中执行 {agent_name} 脚本 ({len(p['code'])} chars)")
            result = executor.run_script(p["code"], filename="agent_script.py")
        elif p.get("script_path"):
            logger.info(f"[Harness.Sandbox] 在沙箱中执行文件: {p['script_path']}")
            result = executor.run_command([sys.executable, p["script_path"]])
        else:
            logger.warning(f"[Harness.Sandbox] {agent_name} 无可执行代码，回退 Django")
            return None  # 交由 Django 执行

        if result.status in (SandboxStatus.SUCCESS,):
            logger.info(
                f"[Harness.Sandbox] 沙箱执行成功 {agent_name} "
                f"exit={result.exit_code} dur={result.duration_seconds:.1f}s "
                f"mem={result.peak_memory_mb:.1f}MB"
            )
            return _audit_step_output({
                "status": "success",
                "response": result.stdout,
                "sandbox": {
                    "used": True,
                    "exit_code": result.exit_code,
                    "duration_seconds": result.duration_seconds,
                    "peak_memory_mb": result.peak_memory_mb,
                },
                "executed_in_sandbox": True,
            })
        else:
            reason = result.error_message or result.status.value
            logger.error(f"[Harness.Sandbox] 沙箱执行失败 {agent_name}: {reason}")
            # 沙箱执行失败（超时/越权/系统错误）→ 不裸回退执行，直接上报失败
            raise RuntimeError(f"沙箱执行被拒绝: {reason}")

    def _call_agent(**kwargs):
        # 合并 params：kwargs 中的 params 为基础，其余键值合并进去
        # 这样自愈策略（AIFixSyntax/AIDiagnose）修改 step_params 时能透传到下游调用
        p = dict(kwargs.get("params", params))
        for k, v in kwargs.items():
            if k not in ("params",):
                p[k] = v
        
        team = state.get("team_id", "default")

        # === ReAct 路径：标记 react=True 或 Capable Agent 自动走 ReAct 循环 ===
        use_react = step.get("react", False) or agent_name in REACT_CAPABLE_AGENTS
        if use_react:
            react_result = _exec_react_step(
                agent_name=agent_name,
                params=p,
                prompt=p.get("prompt", prompt),
                step=step,
                state=state,
            )
            if react_result.get("status") == "success":
                react_result["data"] = react_result.get("response", react_result)
                return react_result
            raise ValueError(react_result.get("response", react_result.get("status", "ReAct 执行失败")))

        # 动态解析 Agent → action（MCP 优先，硬编码回退）
        action = resolve_agent_action(agent_name, team_id=team, auth_token=auth_token)
        
        # === 沙箱优先：execution 或带 code 的步骤，启用沙箱时一律先过底座沙箱 ===
        if sandbox_config.enabled and (agent_name == "execution" or p.get("code") or p.get("script_path")):
            sbox_result = _execute_via_sandbox(agent_name, p)
            if sbox_result is not None:
                return sbox_result
            # 返回 None 表示无代码可执行，继续走 Django（如纯 HTTP 用例执行编排）

        # 步骤间关键数据透传：generator 产生的 case_ids 交给 execution；execution 产生的 execution_id 交给 evaluator
        context = state.get("context", {})
        if agent_name == "execution" and "case_ids" in context:
            p["test_case_ids"] = context["case_ids"]
        if agent_name == "evaluator" and "execution_id" in context:
            p["execution_id"] = context["execution_id"]
        
        # 判断调用路径：MCP tool 还是 Django Agent API
        if _is_mcp_tool(action):
            # 路径 1：通过 MCP ToolGateway 调用
            from app.services.tool_gateway_client import ToolGatewayClient
            client = ToolGatewayClient(
                mcp_url=DJANGO_MCP_URL,
                auth_token=auth_token,
                timeout=AGENT_CONFIG.timeout_seconds,
            )
            # backend /api/mcp/tools/call/ 返回外层结构：
            #   {"tool": "...", "result": {"content": [...], "isError": false, ...}, "is_error": false}
            # ToolGatewayClient.call_tool 目前返回整个外层结构，因此需要取 result["result"]
            result = client.call_tool(
                name=action,
                arguments=p,
                team_id=team,
                user_id=state.get("user_id"),
            )
            raw_result = result.get("result", result)
            if raw_result.get("isError"):
                error_text = raw_result.get("content", [{}])[0].get("text", "MCP 调用失败")
                raise ValueError(error_text)
            return _mcp_result_to_dict(raw_result)
        else:
            # 路径 2：通过 Django Agent API 调用（向后兼容）
            client = DjangoClient(base_url=DJANGO_BASE_URL, auth_token=auth_token,
                                  timeout=AGENT_CONFIG.timeout_seconds)
            return _audit_step_output(client.call_agent(action, p))

    with tracer.start_as_current_span("harness.execute_step") as span:
        span.set_attribute("agent", agent_name)
        span.set_attribute("step_index", step_index)
        span.set_attribute("task_id", task_id)

        # 幂等警告：防止同一次运行中重复执行（仅日志，不阻断）
        idem = get_idempotency_tracker()
        if idem.is_processed(task_id, step_index, agent_name):
            logger.warning(
                f"[Harness.Idempotency] task={task_id} step={step_index} agent={agent_name} "
                f"疑似重复执行，继续但标记"
            )

        try:
            # 工具调用包装：熔断 + 重试（按 agent 隔离熔断器）
            result_data = call_with_robustness(
                _call_agent,
                params=params,
                circuit_name=f"agent:{agent_name}",
                max_retries=2,
            )
            status = "completed" if result_data.get("status") != "failed" else "failed"
            error = None if status == "completed" else result_data.get("error", "执行失败")

            # 标记幂等已处理
            idem.mark_processed(task_id, step_index, agent_name)

            # 把关键结果透传到 context，供后续步骤使用
            if agent_name == "generator" and "case_ids" in result_data:
                state.setdefault("context", {})["case_ids"] = result_data["case_ids"]
            if agent_name == "execution" and "execution_id" in result_data:
                state.setdefault("context", {})["execution_id"] = result_data["execution_id"]
            if agent_name == "search":
                # 从 testcase_search 的结果中提取 case_ids 与原始结果，便于后续展示或执行
                cases = result_data.get("cases", [])
                if cases:
                    case_ids = [c["id"] for c in cases if isinstance(c, dict) and "id" in c]
                    state.setdefault("context", {})["case_ids"] = case_ids
                    state.setdefault("context", {})["search_results"] = cases

        except RetryExhausted as e:
            logger.exception(f"[Harness] {agent_name} 重试耗尽: {e.original_exception}")
            result_data = {"status": "error", "error": f"重试耗尽: {e.original_exception}"}
            status = "failed"
            error = str(e.original_exception)
            span.set_attribute("error", True)
            span.set_attribute("error.message", str(e.original_exception))
        except Exception as e:
            logger.exception(f"[Harness] {agent_name} 执行异常: {e}")
            result_data = {"status": "error", "error": str(e)}
            status = "failed"
            error = str(e)
            span.set_attribute("error", True)
            span.set_attribute("error.message", str(e))

        duration_ms = int((time.time() - start) * 1000)
        workflow_step_duration_seconds.labels(agent=agent_name).observe(duration_ms / 1000.0)
        span.set_attribute("duration_ms", duration_ms)

    # ============================================================
    # 自愈阶段 — 从 Django Harness 迁入
    # ============================================================
    healing_used = False
    if status == "failed" and error:
        logger.info(f"[Harness.SelfHealing] 步骤 {step_index} ({agent_name}) 失败, 尝试自愈...")
        _emit(state, ProgressEvent.HEAL_START, {
            "task_id": task_id, "step_index": step_index,
            "agent": agent_name, "error": error,
        })

        try:
            engine = SelfHealingEngine(max_attempts=2, use_ai=True)
            analysis = ErrorClassifier.classify(error, {
                "step_name": f"{agent_name}_{step_index}",
                "agent": agent_name, "prompt": prompt[:100],
            })

            if analysis.fixable:
                _emit(state, ProgressEvent.HEAL_STRATEGY, {
                    "task_id": task_id, "step_index": step_index,
                    "strategies": analysis.suggested_strategies,
                    "category": analysis.category.value,
                })

                heal_result = engine.heal(
                    step_func=_call_agent,
                    step_params={"params": params},
                    step_name=f"{agent_name}_{step_index}",
                    context={"agent": agent_name},
                )

                if heal_result["status"] == "healed":
                    duration_ms = int((time.time() - start) * 1000)
                    healing_used = True
                    _emit(state, ProgressEvent.HEAL_SUCCESS, {
                        "task_id": task_id, "step_index": step_index,
                        "agent": agent_name, "duration_ms": duration_ms,
                        "healing_record": heal_result.get("healing_record"),
                    })
                    logger.info(f"[Harness.SelfHealing] 步骤 {step_index} 自愈成功!")

                    step_result = {
                        "agent": agent_name, "prompt": prompt,
                        "result": {"status": "success", "healed": True},
                        "duration_ms": duration_ms, "step_index": step_index,
                        "status": "completed", "error": None,
                        "healed": True,
                    }
                    _emit(state, ProgressEvent.STEP_COMPLETE, {
                        "task_id": task_id, "step_index": step_index,
                        "agent": agent_name, "status": "completed",
                        "duration_ms": duration_ms, "healed": True,
                    })
                    span.set_attribute("status", "completed")
                    span.set_attribute("healed", True)
                    return step_result
                else:
                    _emit(state, ProgressEvent.HEAL_FAILED, {
                        "task_id": task_id, "step_index": step_index,
                        "agent": agent_name,
                        "reason": heal_result.get("analysis", {}),
                    })
                    logger.warning(f"[Harness.SelfHealing] 自愈失败: {agent_name}")

        except Exception as heal_err:
            logger.warning(f"[Harness.SelfHealing] 自愈异常: {heal_err}, 返回原始错误")

    span.set_attribute("status", status)
    span.set_attribute("healed", healing_used)

    step_result = {
        "agent": agent_name, "prompt": prompt, "result": result_data,
        "duration_ms": duration_ms, "step_index": step_index,
        "status": status, "error": error,
        "healed": healing_used,
    }

    _emit(state, ProgressEvent.STEP_FAILED if status == "failed" else ProgressEvent.STEP_COMPLETE, {
        "task_id": task_id, "step_index": step_index,
        "agent": agent_name, "status": status,
        "duration_ms": duration_ms, "error": error, "healed": healing_used,
    })

    return step_result


def parallel_orchestrate_node(state: dict) -> dict:
    """
    并行编排节点

    支持断点续跑：
    - 从 state["current_step"] 开始
    - 跳过 state["_completed_steps"] 中已完成的步骤
    - 每执行完一组就保存 checkpoint
    """
    plan = state.get("plan", [])
    current = state.get("current_step", 0)
    task_id = state.get("task_id")
    # 恢复时已完成的步骤索引列表
    completed_steps_set = set(state.get("_completed_steps") or [])

    # 如果有之前的结果（从 checkpoint 恢复），先加载
    all_results = list(state.get("results") or [])

    with tracer.start_as_current_span("harness.orchestrate") as span:
        span.set_attribute("task_id", task_id)
        span.set_attribute("total_steps", len(plan))

        if current >= len(plan):
            result = {
                "current_step": current,
                "plan": plan,
                "results": all_results or [],
                "context": state.get("context", {}),
                "errors": [r["error"] for r in (all_results or []) if r.get("error")],
                **_passthrough_state(state),
            }
            save_checkpoint({**state, **result}, phase="orchestrate",
                            completed_steps=list(completed_steps_set))
            return result

        def get_group(steps_list, start_idx):
            group = []
            if start_idx >= len(steps_list):
                return group
            first_group = steps_list[start_idx].get("parallel_group")
            i = start_idx
            while i < len(steps_list):
                s = steps_list[i]
                if i == start_idx:
                    group.append(s)
                elif s.get("parallel_group") == first_group and first_group is not None:
                    group.append(s)
                else:
                    break
                i += 1
            return group

        index = current
        while index < len(plan):
            group = get_group(plan, index)
            group_indices = [index + gi for gi in range(len(group))]

            # 过滤掉已完成的步骤
            pending_steps = [
                s for i, s in zip(group_indices, group)
                if i not in completed_steps_set
            ]

            if not pending_steps:
                # 整组已完成，跳过
                logger.info(
                    f"[Harness.Parallel] Steps {group_indices} 已完成，跳过 "
                    f"(completed: {sorted(completed_steps_set)})"
                )
                # 标记整组为已完成
                for gi in group_indices:
                    completed_steps_set.add(gi)
                index += len(group)
                continue

            if len(pending_steps) == 1:
                step = pending_steps[0]
                si = step.get("step_index", index)
                logger.info(f"[Harness.Parallel] Step {si+1}/{len(plan)} -> {step['agent']} (serial)")
                result = _execute_single_step(step, state)
                all_results.append(result)
                completed_steps_set.add(si)
            else:
                agents_str = ", ".join(s["agent"] for s in pending_steps)
                logger.info(
                    f"[Harness.Parallel] ParallelGroup({len(pending_steps)}): [{agents_str}] "
                    f"(已跳过 {len(group)-len(pending_steps)} 个已完成)"
                )
                with ThreadPoolExecutor(max_workers=min(len(pending_steps), 4)) as executor:
                    futures = {
                        executor.submit(_execute_single_step, s, state): s
                        for s in pending_steps
                    }
                    for future in as_completed(futures):
                        step_result = future.result()
                        all_results.append(step_result)
                        si = step_result.get("step_index", index)
                        completed_steps_set.add(si)

            # 更新 context
            context = state.get("context", {})
            for r in all_results:
                if r.get("status") == "completed":
                    context[r["agent"]] = r.get("result")

            # 如果启用全流程重试（should_retry 跳回 plan），增加全局计数
            global_retry_count = state.get("_retry_count", 0)

            index += len(group)

            # 每组执行完立即保存 checkpoint（最小化断点损失）
            orchestrate_state = {
                "current_step": index,
                "results": all_results,
                "context": context,
                "errors": [r["error"] for r in all_results if r.get("error")],
            }
            save_checkpoint(
                {**state, **orchestrate_state},
                phase="orchestrate",
                completed_steps=list(completed_steps_set),
                retry_count=global_retry_count,
            )

        return {
            "current_step": index,
            "plan": plan,
            "results": all_results,
            "context": state.get("context", {}),
            "errors": [r["error"] for r in all_results if r.get("error")],
            **_passthrough_state(state),
        }



def verify_node(state: dict) -> dict:
    """Verify 节点：验证执行结果"""
    errors = state.get("errors", [])
    results = state.get("results", [])
    user_request = state.get("user_request", "")
    task_id = state.get("task_id")
    team_id = state.get("team_id", "default")

    _emit(state, ProgressEvent.VERIFY_START, {"task_id": task_id})

    try:
        router = get_llm_router()
        results_text = json.dumps([{"agent": r["agent"], "status": r["status"], "result": r.get("result")} for r in results], ensure_ascii=False)
        messages = [
            {"role": "system", "content": VERIFY_SYSTEM_PROMPT},
            {"role": "user", "content": f"用户需求：{user_request}\n\n执行结果：{results_text}\n\n请验证是否满足需求。"},
        ]
        with tracer.start_as_current_span("harness.verify") as span:
            span.set_attribute("task_id", task_id)
            llm_start = time.time()
            response = call_llm_with_fallback(
                router, messages, task_type="evaluation", fallback_model="deepseek-chat", team_id=team_id
            )
            llm_duration = time.time() - llm_start
            llm_requests_total.labels(provider="auto", model="auto", status="success").inc()
            llm_request_duration_seconds.labels(provider="auto", model="auto").observe(llm_duration)
        verification = _parse_verification(response)
    except Exception as e:
        logger.warning(f"[Harness.Verify] 验证失败: {e}")

        failed_steps = [r for r in results if r.get("status") == "failed"]
        passed = len(failed_steps) == 0 and len(results) > 0
        verification = {
            "passed": passed,
            "score": 1.0 if passed else 0.0,
            "issues": [r.get("error") for r in failed_steps],
            "summary": "自动验证完成" if passed else "存在失败步骤",
        }

    # 后处理：搜索类需求如果 search 步骤成功返回结果，则直接通过
    user_request_lower = (user_request or "").lower()
    search_keywords = ["搜索", "查找", "列出", "看看", "有哪些", "帮我找"]
    is_search_request = any(k in user_request_lower for k in search_keywords)
    search_results = [r for r in results if r.get("agent") == "search" and r.get("status") == "completed"]
    if is_search_request and search_results:
        any_has_results = any(
            r.get("result", {}).get("total", 0) > 0 or r.get("result", {}).get("cases", [])
            for r in search_results
        )
        if any_has_results:
            verification["passed"] = True
            verification["score"] = max(verification.get("score", 0.0), 0.9)
            verification["summary"] = f"已找到与「{user_request}」相关的测试用例。"
            verification["issues"] = []

    final_output = {
        "summary": verification.get("summary", "工作流执行完成"),
        "results": results,
        "passed": verification.get("passed", False),
    }

    _emit(state, ProgressEvent.VERIFY_COMPLETE, verification)
    _emit(state, ProgressEvent.WORKFLOW_COMPLETE, {
        "task_id": task_id,
        "passed": verification.get("passed", False),
        "score": verification.get("score", 0),
        "summary": final_output["summary"],
        "results": final_output["results"],
    })

    # ── 审计：工作流完成 ──
    try:
        audit = get_audit_store()
        audit.write_workflow_event(
            task_id=task_id or "",
            user_id=str(state.get("user_id", "system")),
            team_id=state.get("team_id", "default"),
            stage="verify",
            status="end",
            message=f"工作流完成: {final_output.get('summary', '')[:150]}",
        )
    except Exception:
        pass

    result = {
        "verification": verification,
        "final_output": final_output,
        "plan": state.get("plan", []),
        "results": results,
        **_passthrough_state(state),
    }
    save_checkpoint({**state, **result}, phase="complete")
    return result





def _parse_verification(response_text: str) -> dict:
    """解析验证结果"""
    text = response_text.strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.lower().startswith("json"):
            text = text[4:].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        import re
        match = re.search(r"\{.*?\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    return {"passed": True, "score": 1.0, "issues": [], "summary": "验证完成"}


def should_orchestrate(state: dict) -> Literal["orchestrate", "verify"]:
    plan = state.get("plan", [])
    current = state.get("current_step", 0)
    if current < len(plan):
        return "orchestrate"
    return "verify"


def should_retry(state: dict) -> Literal["plan", "__end__"]:
    verification = state.get("verification", {})
    retry_count = state.get("_retry_count", 0)

    if not verification.get("passed", False):
        failed_count = verification.get("failed_steps", 0)
        if failed_count > 0 and retry_count < MAX_GLOBAL_RETRIES:
            new_retry_count = retry_count + 1
            logger.warning(
                f"[Harness.Verify] {failed_count} 步骤失败，触发重试 "
                f"({new_retry_count}/{MAX_GLOBAL_RETRIES})"
            )
            # 持久化重试计数
            task_id = state.get("task_id")
            if task_id:
                save_checkpoint(
                    {**state, "_retry_count": new_retry_count},
                    phase="plan",
                    completed_steps=[],
                    retry_count=new_retry_count,
                )
            return "plan"
        elif retry_count >= MAX_GLOBAL_RETRIES:
            logger.warning(f"[Harness.Verify] 重试已达上限 ({MAX_GLOBAL_RETRIES})，放弃重试")
    return "__end__"


def entry_router(state: dict) -> Literal["plan", "orchestrate", "verify", "__end__"]:
    """根据 checkpoint 决定工作流入口节点（含重试上限保护）"""
    from langgraph.graph import END

    # 检查全局重试是否超限
    retry_count = state.get("_retry_count", 0)
    if retry_count >= MAX_GLOBAL_RETRIES:
        logger.warning(
            f"[Harness.Resume] 全局重试已达上限 ({retry_count}/{MAX_GLOBAL_RETRIES}), 强制结束"
        )
        return "__end__"

    phase = state.get("__checkpoint_phase")
    if phase == "plan":
        logger.info(f"[Harness.Resume] checkpoint phase=plan, 跳过 Plan 从 Orchestrate 开始")
        return "orchestrate"
    if phase == "orchestrate":
        logger.info(f"[Harness.Resume] checkpoint phase=orchestrate, 从 Orchestrate 继续")
        return "orchestrate"
    if phase == "complete":
        logger.info(f"[Harness.Resume] checkpoint phase=complete, 直接结束")
        return "__end__"
    return "plan"


def build_default_workflow(use_parallel: bool = True):
    from langgraph.graph import StateGraph, END

    workflow = StateGraph(dict)

    workflow.add_node("plan", plan_node)
    workflow.add_node("orchestrate", parallel_orchestrate_node)
    workflow.add_node("verify", verify_node)

    # 条件入口：优先根据 checkpoint 阶段恢复，否则从 plan 开始
    workflow.set_conditional_entry_point(
        entry_router,
        {
            "plan": "plan",
            "orchestrate": "orchestrate",
            "verify": "verify",
            "__end__": END,
        },
    )
    workflow.add_edge("plan", "orchestrate")
    workflow.add_conditional_edges(
        "orchestrate",
        should_orchestrate,
        {"orchestrate": "orchestrate", "verify": "verify"},
    )
    workflow.add_conditional_edges(
        "verify",
        should_retry,
        {"plan": "plan", "__end__": END},
    )

    compiled = workflow.compile()
    logger.info(f"[Harness] 工作流构建完成 (parallel={use_parallel})")
    return compiled


def _build_initial_state(user_request: str, task_id: str, user_id: int,
                         auth_token: str, progress_callback: callable,
                         team_id: str = "default", template_id: str = None):
    """构建初始 state，优先从 checkpoint 恢复"""
    if task_id:
        checkpoint = load_checkpoint(task_id)
        if checkpoint and checkpoint.state:
            logger.info(
                f"[Harness] 从 checkpoint 恢复 task_id={task_id} "
                f"phase={checkpoint.phase} version={checkpoint.version} "
                f"completed_steps={checkpoint.completed_steps}"
            )
            state = dict(checkpoint.state)
            state["progress_callback"] = progress_callback
            state["__checkpoint_phase"] = checkpoint.phase
            state["_completed_steps"] = checkpoint.completed_steps
            state["_retry_count"] = checkpoint.retry_count
            state["_step_retry_counts"] = checkpoint.step_retry_counts
            # 覆盖可能变化的参数（用户重新请求时可能更新）
            state["user_request"] = user_request or state.get("user_request", "")
            state["user_id"] = user_id or state.get("user_id")
            state["auth_token"] = auth_token or state.get("auth_token")
            state["team_id"] = team_id or state.get("team_id", "default")
            state["template_id"] = template_id or state.get("template_id")
            return state

    return {
        "user_request": user_request,
        "task_id": task_id,
        "user_id": user_id,
        "team_id": team_id,
        "template_id": template_id,
        "auth_token": auth_token,
        "progress_callback": progress_callback,
        "__checkpoint_phase": None,
        "_completed_steps": [],
        "_retry_count": 0,
        "_step_retry_counts": {},
    }


def run_workflow_stream(user_request: str, task_id: str = None, user_id: int = None,
                        auth_token: str = None, on_progress=None,
                        team_id: str = "default", template_id: str = None):
    """运行工作流并提供 SSE 进度流（支持 Checkpoint 断点续跑 + 团队模板）"""
    progress_queue = queue_module.Queue()

    def progress_callback(event_type: str, data: dict):
        progress_queue.put({"event": event_type, "data": data})

    initial_state = _build_initial_state(user_request, task_id, user_id, auth_token, progress_callback,
                                         team_id=team_id, template_id=template_id)

    # 如果从 checkpoint 恢复，先通知前端
    if initial_state.get("__checkpoint_phase"):
        completed = initial_state.get("_completed_steps", [])
        progress_callback(ProgressEvent.CHECKPOINT_RESUME, {
            "task_id": task_id,
            "phase": initial_state["__checkpoint_phase"],
            "current_step": initial_state.get("current_step", 0),
            "total_steps": len(initial_state.get("plan", [])),
            "completed_steps": completed,
            "completed_count": len(completed),
            "retry_count": initial_state.get("_retry_count", 0),
        })

    final_state_holder = {}

    error_holder = {}


    with tracer.start_as_current_span("harness.workflow_stream") as span:
        span.set_attribute("task_id", task_id)
        workflow_total.labels(status="started", mode="stream").inc()
        workflow_active.inc()

        def run():
            try:
                wf = build_default_workflow(use_parallel=True)
                result = wf.invoke(initial_state)
                final_state_holder["result"] = result
            except Exception as e:
                logger.exception("[Harness.Stream] 工作流异常")
                error_holder["error"] = str(e)
                progress_callback(ProgressEvent.WORKFLOW_ERROR, {"task_id": task_id, "error": str(e)})
                # ── Webhook 通知：工作流失败 ──
                try:
                    from app.core.webhook_notifier import notify_workflow_error
                    notify_workflow_error(
                        user_request=user_request,
                        error=str(e),
                        task_id=task_id or "",
                        retry_count=initial_state.get("_retry_count", 0),
                    )
                except Exception:
                    pass

        thread = threading.Thread(target=run, daemon=True)
        thread.start()

        try:
            while thread.is_alive() or not progress_queue.empty():
                try:
                    event = progress_queue.get(timeout=0.5)
                    yield event
                except queue_module.Empty:
                    pass

            while not progress_queue.empty():
                try:
                    event = progress_queue.get_nowait()
                    yield event
                except queue_module.Empty:
                    break

            if "result" in final_state_holder:
                workflow_total.labels(status="completed", mode="stream").inc()
                # 工作流成功完成，清理 checkpoint
                cleanup_checkpoint(task_id)
                yield {
                    "event": "workflow_complete",
                    "data": final_state_holder["result"].get("final_output", {}),
                }
                # ── Webhook 通知：工作流完成（stream 模式）──
                try:
                    from app.core.webhook_notifier import notify_workflow_complete
                    final_result = final_state_holder.get("result", {})
                    final_output = final_result.get("final_output", {})
                    results = final_result.get("results", [])
                    total_duration = sum(r.get("duration_ms", 0) for r in results)
                    notify_workflow_complete(
                        user_request=user_request,
                        passed=final_output.get("passed", False),
                        score=final_output.get("score", 0),
                        summary=final_output.get("summary", "工作流执行完成"),
                        steps_count=len(results),
                        duration_ms=total_duration,
                        task_id=task_id or "",
                    )
                except Exception:
                    pass
            elif "error" in error_holder:
                workflow_total.labels(status="failed", mode="stream").inc()
                span.set_attribute("error", True)
                span.set_attribute("error.message", error_holder["error"])
                # 仅在不支持重试时清理；否则保留 checkpoint 供用户手动 resume
                retry_count = initial_state.get("_retry_count", 0)
                if retry_count >= MAX_GLOBAL_RETRIES:
                    cleanup_checkpoint(task_id)
                    logger.info(f"[Harness] 重试已达上限，清理 checkpoint: {task_id}")
                yield {
                    "event": "error",
                    "data": {
                        "message": error_holder["error"],
                        "retry_count": retry_count,
                        "max_retries": MAX_GLOBAL_RETRIES,
                        "can_resume": retry_count < MAX_GLOBAL_RETRIES,
                    },
                }
        finally:
            workflow_active.dec()


# ============================================================
# Supervisor-Worker 多代理编排（复用上文流式/SSE 机制）
# ============================================================

def run_supervisor_stream(user_request: str, task_id: str = None, user_id: int = None,
                          auth_token: str = None, on_progress=None,
                          team_id: str = "default", template_id: str = None,
                          model: str = None):
    """
    Supervisor-Worker 编排的 SSE 流式入口，与 run_workflow_stream 同机制。
    区别：内部不再是固定 LangGraph 步骤，而是由 Supervisor Agent 动态调度 Worker。
    """
    if task_id is None:
        task_id = str(uuid.uuid4())

    progress_queue = queue_module.Queue()

    def progress_callback(event_type: str, data: dict):
        progress_queue.put({"event": event_type, "data": data})

    from app.core.supervisor import run_supervisor

    workflow_total.labels(status="started", mode="supervisor").inc()
    workflow_active.inc()

    result_holder = {}
    error_holder = {}

    with tracer.start_as_current_span("harness.supervisor_stream") as span:
        span.set_attribute("task_id", task_id)
        span.set_attribute("team_id", team_id)

        def run():
            try:
                result = run_supervisor(
                    user_request=user_request,
                    task_id=task_id,
                    user_id=user_id,
                    auth_token=auth_token,
                    team_id=team_id,
                    template_id=template_id,
                    model=model,
                    progress_callback=progress_callback,
                )
                result_holder["result"] = result
            except Exception as e:
                logger.exception("[Supervisor.Stream] 编排异常")
                error_holder["error"] = str(e)
                progress_callback(ProgressEvent.WORKFLOW_ERROR, {"task_id": task_id, "error": str(e)})

        thread = threading.Thread(target=run, daemon=True)
        thread.start()

        try:
            while thread.is_alive() or not progress_queue.empty():
                try:
                    event = progress_queue.get(timeout=0.5)
                    yield event
                except queue_module.Empty:
                    pass

            while not progress_queue.empty():
                try:
                    event = progress_queue.get_nowait()
                    yield event
                except queue_module.Empty:
                    break

            if "result" in result_holder:
                workflow_total.labels(status="completed", mode="supervisor").inc()
                yield {
                    "event": "supervisor_complete",
                    "data": result_holder["result"],
                }
            elif "error" in error_holder:
                workflow_total.labels(status="failed", mode="supervisor").inc()
                yield {
                    "event": "error",
                    "data": {
                        "message": error_holder["error"],
                        "can_resume": False,
                    },
                }
        finally:
            workflow_active.dec()


def run_supervisor_sync(user_request: str, task_id: str = None, user_id: int = None,
                        auth_token: str = None, team_id: str = "default",
                        template_id: str = None, model: str = None) -> dict:
    """
    Supervisor-Worker 编排的同步入口（非流式，返回完整结果 dict）。
    """
    if task_id is None:
        task_id = str(uuid.uuid4())
    from app.core.supervisor import run_supervisor
    return run_supervisor(
        user_request=user_request,
        task_id=task_id,
        user_id=user_id,
        auth_token=auth_token,
        team_id=team_id,
        template_id=template_id,
        model=model,
    )

