"""评测工具（替代 Django EvaluatorAgent + evaluate API）。

对生成内容 / 答案做质量评测。纯 LLM 驱动，无数据库依赖。
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
        "content": {"type": "string", "description": "待评测内容"},
        "reference": {"type": "string", "description": "参考答案（可选）"},
        "criteria": {"type": "array", "items": {"type": "string"}, "description": "评测维度"},
    },
    "required": ["content"],
}


@register_tool(
    name="evaluate",
    description="对内容质量进行多维度评测并返回分数与改进建议",
    input_schema=_INPUT_SCHEMA,
    category="evaluation",
    agent_type="evaluator",
)
def evaluate(
    content: str,
    reference: str = "",
    criteria: Optional[list] = None,
) -> dict:
    if not content:
        return {"status": "failed", "error": "content 不能为空", "data": {}, "stats": {}}

    criteria = criteria or ["正确性", "完整性", "清晰度"]
    prompt = (
        f"请对以下内容进行质量评测。\n评测维度：{', '.join(criteria)}\n"
        f"待评测内容：\n{content}\n"
    )
    if reference:
        prompt += f"参考答案：\n{reference}\n"
    prompt += (
        "输出 JSON 对象，包含 score(0-1)、issues(数组)、summary(字符串)。"
        "只输出 JSON，不要解释。"
    )

    router = get_llm_router()
    try:
        response = router.chat(messages=[
            {"role": "system", "content": "你是严格的评测专家，只输出 JSON 评测结果。"},
            {"role": "user", "content": prompt},
        ], task_type="evaluation")
    except Exception as e:
        logger.error(f"[evaluate] LLM 调用失败: {e}")
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
            "score": result.get("score", 0.0),
            "issues": result.get("issues", []),
            "summary": result.get("summary", "评测完成"),
        },
        "stats": {"criteria": criteria},
    }
