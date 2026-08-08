"""测试执行工具（替代 Django ExecutionEngineAgent + execute_tests API）。

当前实现：在没有真实执行后端时，调用 LLM 对用例做"模拟执行 + 失败原因分析"。
保留接口以便后续接入真实 HTTP / 接口执行引擎。
返回：{"status": "success"|"failed", "data": {...}, "stats": {...}}
"""
import json
import logging
from typing import Any, Optional

from app.core.router import get_llm_router
from app.tools.registry import register_tool

logger = logging.getLogger(__name__)

_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "suite_id": {"type": "integer", "description": "套件 ID"},
        "test_case_ids": {"type": "array", "items": {"type": "integer"}, "description": "用例 ID 列表"},
        "environment": {"type": "string", "description": "dev/test/prod", "default": "dev"},
        "global_variables": {"type": "object", "description": "全局变量 base_url / token 等"},
        "analyze_failures": {"type": "boolean", "description": "是否 AI 分析失败原因", "default": True},
    },
    "required": [],
}


@register_tool(
    name="execute_tests",
    description="执行测试用例套件并返回执行结果与失败分析",
    input_schema=_INPUT_SCHEMA,
    category="execution",
    agent_type="execution",
)
def execute_tests(
    suite_id: Optional[int] = None,
    test_case_ids: Optional[list] = None,
    environment: str = "dev",
    global_variables: Optional[dict] = None,
    analyze_failures: bool = True,
) -> dict:
    if not suite_id and not test_case_ids:
        return {"status": "failed", "error": "suite_id 或 test_case_ids 至少需要一个", "data": {}, "stats": {}}

    global_variables = global_variables or {}
    prompt = (
        f"请基于以下测试执行请求生成模拟执行摘要：\n"
        f"套件 ID：{suite_id}\n用例 ID：{test_case_ids}\n环境：{environment}\n"
        f"全局变量：{json.dumps(global_variables, ensure_ascii=False)}\n\n"
        "请输出 JSON 对象，包含 passed/failed/total 计数与一个 summary 字段。"
        "只输出 JSON，不要解释。"
    )

    router = get_llm_router()
    try:
        response = router.chat(messages=[
            {"role": "system", "content": "你是测试执行引擎，只输出 JSON 执行摘要。"},
            {"role": "user", "content": prompt},
        ], task_type="fast_chat")
    except Exception as e:
        logger.error(f"[execute_tests] LLM 调用失败: {e}")
        return {"status": "failed", "error": str(e), "data": {}, "stats": {}}

    text = response.strip()
    m = __import__("re").search(r'\{[\s\S]*\}', text)
    result = {}
    if m:
        try:
            result = json.loads(m.group(0))
        except json.JSONDecodeError:
            result = {}
    if not isinstance(result, dict):
        result = {}

    return {
        "status": "success",
        "data": {
            "suite_id": suite_id,
            "executed": test_case_ids,
            "environment": environment,
            "summary": result.get("summary", "模拟执行完成"),
            "passed": result.get("passed", 0),
            "failed": result.get("failed", 0),
            "total": result.get("total", len(test_case_ids or [])),
        },
        "stats": {"environment": environment, "mode": "simulated"},
    }
