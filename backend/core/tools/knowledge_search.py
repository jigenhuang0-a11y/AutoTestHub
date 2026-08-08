"""
知识库检索工具 — Agent 可用它搜索相关文档

使用 MilvusStore + 本地/远程 Embedding 进行向量检索。
支持自动降级：Milvus 不可用时返回空结果（不影响 Agent 主流程）。

修复记录:
- v2.0: 修复 knowledge_base.vector_store 模块不存在的 Bug，
        改用 MilvusStore + DashScopeEmbeddings/本地 Embedding
"""

import logging
import os
from typing import List, Dict, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class KnowledgeSearchResult(BaseModel):
    """知识检索结果"""
    content: str = Field(description="检索到的文本内容")
    source: str = Field(description="来源文档名")
    score: float = Field(description="相似度分数 0-1")
    metadata: dict = Field(default_factory=dict, description="额外元数据")


class KnowledgeSearchTool:
    """
    知识库搜索工具

    供 Agent 在生成用例/脚本时检索历史文档、接口定义、业务规则等。

    检索流程:
        1. 文本 → Embedding（DashScope 或本地模型）
        2. 向量 → Milvus 检索 Top-K
        3. 返回结果 → Agent Prompt 注入
    """

    name = "knowledge_search"
    description = (
        "搜索知识库中的文档，获取相关上下文。"
        "用于了解业务规则、接口定义、历史用例格式等。"
    )

    def __init__(self, collection_name: str = "ai_test_knowledge", user_id: int = None):
        self.collection_name = collection_name
        self.user_id = user_id
        self._embedding_model = None

    def _get_embedding_model(self):
        """懒加载 Embedding 模型（优先本地，降级 DashScope）"""
        if self._embedding_model is not None:
            return self._embedding_model

        # 策略 1：尝试本地 sentence-transformers（隐私优先）
        try:
            from langchain_community.embeddings import HuggingFaceEmbeddings
            model_name = os.getenv(
                "LOCAL_EMBEDDING_MODEL",
                "BAAI/bge-small-zh-v1.5"  # 中文轻量模型，512维，~130MB
            )
            self._embedding_model = HuggingFaceEmbeddings(
                model_name=model_name,
                model_kwargs={"device": "cpu"},
                encode_kwargs={"normalize_embeddings": True},
            )
            logger.info(f"[KnowledgeSearch] 使用本地 Embedding 模型: {model_name}")
            return self._embedding_model
        except Exception as e:
            logger.debug(f"[KnowledgeSearch] 本地 Embedding 不可用 ({e})，尝试 DashScope API")

        # 策略 2：DashScope API
        try:
            from knowledge_base.services import DashScopeEmbeddings
            self._embedding_model = DashScopeEmbeddings()
            logger.info("[KnowledgeSearch] 使用 DashScope Embedding API")
            return self._embedding_model
        except Exception as e:
            logger.warning(f"[KnowledgeSearch] DashScope Embedding 也不可用 ({e})")
            self._embedding_model = False
            return None

    def _get_milvus_store(self):
        """懒加载 MilvusStore（容错，不可用时返回 None）"""
        try:
            from core.tools.milvus_store import get_milvus_store
            store = get_milvus_store(collection_name=self.collection_name)
            health = store.health_check()
            if health.get("status") != "ok":
                logger.warning(f"[KnowledgeSearch] Milvus 不健康: {health}")
                return None
            return store
        except Exception as e:
            logger.warning(f"[KnowledgeSearch] Milvus 不可用: {e}")
            return None

    async def search(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict] = None,
        kb_id: Optional[int] = None,
    ) -> List[KnowledgeSearchResult]:
        """
        执行向量检索（异步兼容）

        Args:
            query: 检索查询文本
            top_k: 返回结果数量
            filters: 元数据过滤条件（预留，当前通过 kb_id 过滤）
            kb_id: 知识库 ID，用于多知识库隔离

        Returns:
            检索结果列表
        """
        try:
            # 1. 获取 Embedding 模型
            emb_model = self._get_embedding_model()
            if emb_model is None or emb_model is False:
                logger.warning("[KnowledgeSearch] 无可用 Embedding 模型")
                return []

            # 2. 获取 Milvus Store
            store = self._get_milvus_store()
            if store is None:
                logger.warning("[KnowledgeSearch] Milvus 不可用")
                return []

            # 3. 文本 → 向量
            query_vector = emb_model.embed_query(query)

            # 4. Milvus 搜索
            raw_results = store.search(
                query_vector=query_vector,
                top_k=top_k,
                kb_id=kb_id,
                similarity_threshold=0.3,  # 过滤无关结果
            )

            # 5. 转换为标准结果格式
            return [
                KnowledgeSearchResult(
                    content=r.get("content", ""),
                    source=r.get("metadata", {}).get("doc_id", "unknown"),
                    score=r.get("score", 0.0),
                    metadata=r.get("metadata", {}),
                )
                for r in raw_results
            ]

        except Exception as e:
            logger.warning(f"[KnowledgeSearch] 检索失败（不影响主流程）: {e}")
            return []

    def format_for_prompt(self, results: List[KnowledgeSearchResult]) -> str:
        """将检索结果格式化为 Prompt 可用的文本"""
        if not results:
            return "（知识库中未找到相关文档）"

        parts = []
        for i, r in enumerate(results, 1):
            parts.append(
                f"【参考文档 {i}】来源: {r.source} | 相关度: {r.score:.2f}\n{r.content[:2000]}"
            )
        return "\n\n".join(parts)

    def execute(self, action: str = None, **kwargs) -> dict:
        """MCP 统一入口（同步兼容）"""
        if action == "knowledge_search":
            query = kwargs.get("query", "")
            top_k = kwargs.get("top_k", 5)
            kb_id = kwargs.get("kb_id", None)
            try:
                import asyncio
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None

                if loop and loop.is_running():
                    # 已在 async 上下文中，创建新 loop 执行
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(
                            lambda: asyncio.run(self.search(query=query, top_k=top_k, kb_id=kb_id))
                        )
                        results = future.result(timeout=30)
                else:
                    results = asyncio.run(self.search(query=query, top_k=top_k, kb_id=kb_id))

                return {
                    "results": [
                        {
                            "content": r.content,
                            "source": r.source,
                            "score": r.score,
                            "metadata": r.metadata,
                        }
                        for r in results
                    ]
                }
            except Exception as e:
                logger.warning(f"[KnowledgeSearch.execute] 失败: {e}")
                return {"results": []}
        return {"error": f"unknown action: {action}"}

    def to_openai_tool(self) -> dict:
        """返回 OpenAI 兼容的 tool schema"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "在知识库中搜索的关键词或问题",
                        },
                        "top_k": {
                            "type": "integer",
                            "description": "返回结果数量，默认 5",
                            "default": 5,
                        },
                        "kb_id": {
                            "type": "integer",
                            "description": "知识库 ID，用于多知识库隔离（可选）",
                        },
                    },
                    "required": ["query"],
                },
            },
        }


# ================================================================
# 单例
# ================================================================

_knowledge_tool: Optional[KnowledgeSearchTool] = None


def get_knowledge_tool() -> KnowledgeSearchTool:
    """获取 KnowledgeSearchTool 单例"""
    global _knowledge_tool
    if _knowledge_tool is None:
        _knowledge_tool = KnowledgeSearchTool()
    return _knowledge_tool
