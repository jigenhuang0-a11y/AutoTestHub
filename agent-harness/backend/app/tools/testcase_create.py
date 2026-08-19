"""用例生成工具（替代 Django TestCaseGeneratorAgent + generate_testcases API）。

纯本地实现：构建 prompt -> 调 LLM（带重试）-> 解析 JSON -> 校验。
不依赖 Django / 数据库。返回结构兼容 workflow._execute_single_step：
    {"status": "success"|"failed", "data": [...], "stats": {...}, "error": "..."}
"""
import json
import logging
import re
from pathlib import Path
from typing import Any, Optional

from app.core.router import get_llm_router
from app.tools.registry import register_tool

logger = logging.getLogger(__name__)


_SYSTEM_PROMPT = (
    "你是资深 API 测试工程师。根据用户需求生成结构化测试用例，"
    "严格按 JSON 数组格式输出，不要 markdown 代码块，不要任何解释文字。"
)

_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "requirement": {"type": "string", "description": "需求描述"},
        "strategy": {"type": "string", "description": "standard/api_only/business/quick"},
        "case_count": {"type": "integer", "description": "生成用例数量", "default": 10},
        "knowledge_context": {"type": "string", "description": "可选知识上下文"},
        "extra_context": {"type": "string", "description": "可选额外约束"},
    },
    "required": ["requirement"],
}


def _build_user_prompt(requirement: str, strategy: str, case_count: int,
                       knowledge_context: str, extra_context: str) -> str:
    parts = [
        f"需求：{requirement}",
        f"策略：{strategy}",
        f"请生成 {case_count} 个测试用例。",
    ]
    if knowledge_context:
        parts.append(f"知识上下文：\n{knowledge_context}")
    if extra_context:
        parts.append(f"额外约束：\n{extra_context}")
    parts.append(
        '输出 JSON 数组，每个元素字段：'
        '{"title","description","api_endpoint","method","headers","request_body",'
        '"expected_response","assertion_rules","priority","tags","assertions"}'
    )
    return "\n\n".join(parts)


def _minimal_prompt(requirement: str, case_count: int) -> tuple[str, str]:
    system = (
        "你是 API 测试工程师。只输出 JSON 数组，不可输出任何额外文字、"
        "markdown 标记或解释。api_endpoint 如不确定填 \"TBD\"。"
    )
    user = (
        f"请为以下需求生成 {case_count} 个测试用例：\n\n「{requirement}」\n\n"
        "严格按此 JSON 数组格式输出（只输出 JSON）：\n"
        '[{"title":"用例标题","description":"描述","api_endpoint":"TBD","method":"POST",'
        '"headers":{},"request_body":{},"expected_response":{"status_code":200},'
        '"assertion_rules":[{"field":"status_code","operator":"equals","expected":200}],'
        '"priority":"P1","tags":["标签"],"assertions":"断言说明"}]'
    )
    return system, user


def _extract_json(text: str) -> Any:
    text = text.strip()
    if not text:
        return None
    # markdown 代码块
    m = re.search(r'```(?:json)?\s*\n?([\s\S]*?)\n?```', text)
    if m:
        text = m.group(1).strip()
    # 平衡括号提取
    for bracket in ('[', '{'):
        ob, cb = ('[', ']') if bracket == '[' else ('{', '}')
        start = text.find(ob)
        if start == -1:
            continue
        depth = 0
        in_str = False
        esc = False
        for i in range(start, len(text)):
            ch = text[i]
            if esc:
                esc = False
                continue
            if ch == '\\':
                esc = True
                continue
            if ch == '"':
                in_str = not in_str
                continue
            if in_str:
                continue
            if ch == ob:
                depth += 1
            elif ch == cb:
                depth -= 1
                if depth == 0:
                    try:
                        parsed = json.loads(text[start:i + 1])
                        return parsed if isinstance(parsed, list) else [parsed]
                    except json.JSONDecodeError:
                        break
    # 直接尝试
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, list) else [parsed]
    except json.JSONDecodeError:
        return None


def _validate(cases: list) -> list:
    valid = []
    for case in cases:
        if not isinstance(case, dict) or not case.get("title") or not case.get("method"):
            continue
        method = str(case.get("method", "GET")).upper()
        if method not in ("GET", "POST", "PUT", "DELETE", "PATCH"):
            method = "GET"
        valid.append({
            "title": str(case.get("title", ""))[:200],
            "description": str(case.get("description", "")),
            "api_endpoint": str(case.get("api_endpoint", "")),
            "method": method,
            "headers": case.get("headers") if isinstance(case.get("headers"), dict) else {},
            "request_body": case.get("request_body") if isinstance(case.get("request_body"), dict) else {},
            "expected_response": case.get("expected_response") if isinstance(case.get("expected_response"), dict) else {},
            "assertion_rules": case.get("assertion_rules") if isinstance(case.get("assertion_rules"), list) else [],
            "priority": case.get("priority", "P2") if case.get("priority") in ("P0", "P1", "P2", "P3") else "P2",
            "tags": case.get("tags") if isinstance(case.get("tags"), list) else [],
            "assertions": str(case.get("assertions", "")),
        })
    return valid


@register_tool(
    name="generate_testcases",
    description="根据需求描述自动生成结构化测试用例",
    input_schema=_INPUT_SCHEMA,
    category="generation",
    agent_type="generator",
)
def generate_testcases(
    requirement: str,
    strategy: str = "standard",
    case_count: int = 10,
    knowledge_context: str = "",
    extra_context: str = "",
) -> dict:
    if not requirement:
        return {"status": "failed", "error": "requirement 不能为空", "data": [], "stats": {}}

    router = get_llm_router()
    system = _SYSTEM_PROMPT
    user = _build_user_prompt(requirement, strategy, case_count, knowledge_context, extra_context)

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = router.chat(messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ], task_type="ai_testcase")
        except Exception as e:
            logger.error(f"[generate_testcases] LLM 调用失败: {e}")
            return {"status": "failed", "error": str(e), "data": [], "stats": {}}

        cases = _extract_json(response) or []
        valid = _validate(cases)
        if valid:
            return {
                "status": "success",
                "data": valid,
                "stats": {"total": len(cases), "valid": len(valid), "strategy": strategy, "retries": attempt},
            }
        logger.warning(f"[generate_testcases] 第 {attempt + 1} 次解析失败")

        if attempt < max_retries - 1:
            system, user = _minimal_prompt(requirement, case_count)

    return {"status": "failed", "error": "未能解析出有效用例", "data": [], "stats": {}}
