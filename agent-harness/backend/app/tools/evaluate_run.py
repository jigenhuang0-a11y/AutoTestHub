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

# 测试场景专用评测维度（AI 测试平台默认使用）
TESTING_CRITERIA = [
    "用例覆盖度：是否覆盖了正常/边界/异常场景，关键路径是否遗漏",
    "断言与校验有效性：是否包含可验证的预期结果、断言或检查点，校验是否具体可执行",
    "可执行性：步骤是否清晰、可直接转化为自动化脚本或手工测试动作",
    "与参考材料一致性（忠实度）：是否严格基于检索/参考内容，未编造不存在的接口/字段/结论",
    "清晰度与规范性：术语准确、结构清晰、符合测试文档规范",
]

_GENERAL_CRITERIA = ["正确性", "完整性", "清晰度"]

_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "content": {"type": "string", "description": "待评测内容"},
        "reference": {"type": "string", "description": "参考答案（可选）"},
        "criteria": {"type": "array", "items": {"type": "string"}, "description": "评测维度"},
        "domain": {"type": "string", "description": "领域，testing=测试场景专用维度，general=通用维度"},
    },
    "required": ["content"],
}


@register_tool(
    name="evaluate",
    description="对内容质量进行多维度评测并返回分数与改进建议（测试场景专用）",
    input_schema=_INPUT_SCHEMA,
    category="evaluation",
    agent_type="evaluator",
)
def evaluate(
    content: str,
    reference: str = "",
    criteria: Optional[list] = None,
    domain: str = "testing",
) -> dict:
    if not content:
        return {"status": "failed", "error": "content 不能为空", "data": {}, "stats": {}}

    if criteria:
        used_criteria = list(criteria)
    else:
        used_criteria = TESTING_CRITERIA if domain == "testing" else _GENERAL_CRITERIA
    prompt = (
        f"请对以下内容进行质量评测。\n评测维度：\n"
        + "\n".join(f"- {c}" for c in used_criteria)
        + f"\n待评测内容：\n{content}\n"
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
            "criteria": used_criteria,
        },
        "stats": {"criteria": used_criteria, "domain": domain},
    }
