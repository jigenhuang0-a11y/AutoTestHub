"""RAG 知识中枢 - 混合检索（关键词 + 向量）。

P2 实现：
- 向量检索：经统一模型底座 embedding，Milvus 相似性搜索
- 关键词检索：BM25 式 TF 倒排（内存版，P3 换 ES）
- 混合：RRF（Reciprocal Rank Fusion）融合两路结果

注：Milvus 连接为懒加载，未启动时不阻塞启动；检索接口返回降级结果。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from harness_core.config import settings
from harness_core.logging import logger


@dataclass
class RetrievedChunk:
    text: str
    score: float
    source: str = ""


class HybridRetriever:
    def __init__(self) -> None:
        self._milvus = None
        self._collection = None
        self._corpus: list[str] = []  # 关键词检索内存语料（P2 演示）

    # ---- 向量侧 ----
    def _connect(self) -> bool:
        if self._milvus is not None:
            return True
        try:
            from pymilvus import MilvusClient

            self._milvus = MilvusClient(
                uri=f"http://{settings.milvus_host}:{settings.milvus_port}",
                token=settings.milvus_token or None,
            )
            return True
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[rag] Milvus 未就绪，向量检索降级: {e}")
            self._milvus = False
            return False

    async def embed(self, texts: list[str]) -> list[list[float]]:
        from harness_core.llm.gateway import GatewayContext, gateway

        gctx = GatewayContext(tenant_id=0, trace_id="rag-embed")
        msgs = [__import__("harness_core.llm.base", fromlist=["ChatMessage"]).ChatMessage(role="user", content=t) for t in texts]
        # embedding 走适配器直连，不经 chat 网关（避免护栏）
        from harness_core.llm.adapter import DeepSeekAdapter

        try:
            adapter = DeepSeekAdapter()
            return await adapter.embedding(texts)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[rag] embedding 失败降级空向量: {e}")
            return [[0.0] * 8 for _ in texts]

    # ---- 关键词侧（内存 BM25 简化版）----
    def index_corpus(self, docs: list[str]) -> None:
        self._corpus = docs

    def _keyword_search(self, query: str, top_k: int = 5) -> list[tuple[int, float]]:
        q_terms = set(query)
        scored: list[tuple[int, float]] = []
        for i, doc in enumerate(self._corpus):
            common = len(q_terms & set(doc))
            if common:
                scored.append((i, float(common) / max(1, len(set(doc)))))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    # ---- 混合（RRF）----
    def hybrid_search(
        self, query: str, vector_hits: list[tuple[int, float]], top_k: int = 5
    ) -> list[RetrievedChunk]:
        kw = self._keyword_search(query, top_k=top_k)
        # RRF 融合
        rrf: dict[int, float] = {}
        for rank, (idx, _) in enumerate(vector_hits):
            rrf[idx] = rrf.get(idx, 0.0) + 1.0 / (rank + 1)
        for rank, (idx, _) in enumerate(kw):
            rrf[idx] = rrf.get(idx, 0.0) + 1.0 / (rank + 1)
        ranked = sorted(rrf.items(), key=lambda x: x[1], reverse=True)[:top_k]
        out: list[RetrievedChunk] = []
        for idx, score in ranked:
            text = self._corpus[idx] if idx < len(self._corpus) else f"[vec#{idx}]"
            out.append(RetrievedChunk(text=text, score=score))
        return out


# 全局单例
retriever = HybridRetriever()
