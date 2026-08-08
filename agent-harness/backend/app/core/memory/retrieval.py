"""
记忆检索器 — 整合三层记忆来源（底座版）

简化实现：分别调用 short_term、long_term 的搜索能力，合并去重后返回。
"""

from typing import List
from app.core.memory.base import MemorySearchResult


class MemoryRetrieval:
    """
    记忆检索器。

    使用方式:
        retrieval = MemoryRetrieval(short_term=stm, long_term=ltm, working=wm)
        results = retrieval.search("用户偏好", top_k=10)
    """

    def __init__(self, short_term, long_term, working):
        self.short_term = short_term
        self.long_term = long_term
        self.working = working

    def search(self, query: str, top_k: int = 10) -> List[MemorySearchResult]:
        """跨三层记忆搜索并合并结果"""
        results = []
        seen_ids = set()

        # 1. 短期记忆
        if self.short_term:
            results.extend(self.short_term.search(query, top_k=top_k))

        # 2. 长期记忆
        if self.long_term:
            results.extend(self.long_term.recall(query, top_k=top_k))

        # 去重
        deduped = []
        for r in results:
            if r.entry.id not in seen_ids:
                seen_ids.add(r.entry.id)
                deduped.append(r)
            if len(deduped) >= top_k:
                break
        return deduped

    def retrieve(self, query: str, team_id: str = None, limit: int = 10) -> List[MemorySearchResult]:
        """manager.py 调用的检索入口"""
        return self.search(query, top_k=limit)

    def get_context(self, query: str, top_k: int = 5) -> str:
        """返回适合注入 LLM 上下文的字符串"""
        results = self.search(query, top_k=top_k)
        if not results:
            return ""
        lines = []
        for r in results:
            lines.append(f"[{r.source}] {r.entry.content}")
        return "\n".join(lines)
