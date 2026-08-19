"""数据工厂工具（替代 Django DataFactoryAgent + generate_data API）。

根据业务域 / 字段定义生成测试数据。纯 LLM 驱动，无数据库依赖。
返回：{"status": "success"|"failed", "data": [...], "stats": {...}}
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
        "business_domain": {"type": "string", "description": "业务域 order/user/logistics/after_sales"},
        "fields": {"type": "array", "description": "自定义字段定义", "items": {"type": "object"}},
        "strategy": {"type": "string", "description": "smart/boundary/template", "default": "smart"},
        "record_count": {"type": "integer", "description": "生成数量", "default": 10},
        "extra_context": {"type": "string", "description": "额外约束"},
    },
    "required": [],
}


@register_tool(
    name="generate_data",
    description="根据业务域或字段定义生成结构化测试数据",
    input_schema=_INPUT_SCHEMA,
    category="generation",
    agent_type="data_factory",
)
def generate_data(
    business_domain: str = "",
    fields: Optional[list] = None,
    strategy: str = "smart",
    record_count: int = 10,
    extra_context: str = "",
) -> dict:
    if not business_domain and not fields:
        return {"status": "failed", "error": "business_domain 或 fields 至少需要一个", "data": [], "stats": {}}

    fields_desc = json.dumps(fields, ensure_ascii=False) if fields else ""
    prompt = (
        f"请为以下业务生成 {record_count} 条测试数据。\n"
        f"业务域：{business_domain or '自定义'}\n"
        f"策略：{strategy}\n"
    )
    if fields_desc:
        prompt += f"字段定义：{fields_desc}\n"
    if extra_context:
        prompt += f"额外约束：{extra_context}\n"
    prompt += (
        "以 JSON 数组输出，每个元素为一个数据记录对象。"
        "只输出 JSON 数组，不要任何解释或 markdown 标记。"
    )

    router = get_llm_router()
    try:
        response = router.chat(messages=[
            {"role": "system", "content": "你是测试数据生成专家，只输出 JSON 数组。"},
            {"role": "user", "content": prompt},
        ], task_type="data_factory")
    except Exception as e:
        logger.error(f"[generate_data] LLM 调用失败: {e}")
        return {"status": "failed", "error": str(e), "data": [], "stats": {}}

    # 简单 JSON 提取
    text = response.strip()
    m = __import__("re").search(r'\[[\s\S]*\]', text)
    records = []
    if m:
        try:
            records = json.loads(m.group(0))
        except json.JSONDecodeError:
            records = []
    if not isinstance(records, list):
        records = []

    return {
        "status": "success" if records else "failed",
        "data": records,
        "stats": {"saved": len(records), "business_domain": business_domain, "strategy": strategy},
    }
