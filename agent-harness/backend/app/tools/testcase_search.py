"""用例搜索工具（替代 Django testcase_search action）。

轻量实现：当前在无向量库时返回空结果（与 Django 知识库未配置时行为一致），
保留接口与团队命名空间（team_id）以便后续接入 RAG。
返回结构兼容 workflow：{"status": "success"|"failed", "data": [...], "stats": {...}}
"""
import logging
from typing import Optional

from app.tools.registry import register_tool

logger = logging.getLogger(__name__)

_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {"type": "string", "description": "搜索关键词"},
        "limit": {"type": "integer", "description": "返回条数", "default": 10},
        "team_id": {"type": "string", "description": "团队 ID（命名空间隔离）"},
    },
    "required": ["query"],
}


@register_tool(
    name="testcase_search",
    description="按关键词搜索已有测试用例 / 知识",
    input_schema=_INPUT_SCHEMA,
    category="retrieval",
    agent_type="search",
)
def testcase_search(query: str, limit: int = 10, team_id: Optional[str] = None) -> dict:
    if not query:
        return {"status": "failed", "error": "query 不能为空", "data": [], "stats": {}}
    # TODO: 接入向量检索（Milvus）后填充真实结果。
    # 当前返回空（与 Django 知识库未配置时行为一致，不影响编排链路）。
    logger.info(f"[testcase_search] query={query!r} team_id={team_id} (RAG 未接入，返回空)")
    return {
        "status": "success",
        "data": [],
        "stats": {"query": query, "returned": 0, "team_id": team_id},
    }
