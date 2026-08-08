"""
短期记忆 — 当前会话的消息缓冲（底座版）

简化实现：使用内存列表保存最近记忆条目，按 token 数量做滑动窗口。
"""

import logging
import uuid
from typing import List, Optional
from datetime import datetime
from app.core.memory.base import MemoryEntry, MemorySearchResult, MemoryType, MemoryImportance

logger = logging.getLogger(__name__)


class ShortTermMemory:
    """
    会话级短期记忆。

    使用方式:
        stm = ShortTermMemory(max_tokens=4000)
        stm.add_message("user", "hello")
        results = stm.search("hello", top_k=5)
    """

    def __init__(self, max_tokens: int = 4000):
        self.max_tokens = max_tokens
        self._messages: List[dict] = []
        self._entries: List[MemoryEntry] = []
        self._current_tokens = 0

    def add_message(self, role: str, content: str) -> None:
        """添加一条消息（对话历史）"""
        self._messages.append({"role": role, "content": content, "time": datetime.now().isoformat()})
        self._current_tokens += max(1, self._estimate_tokens(content))
        self._gc()

    def add(self, entry: MemoryEntry) -> None:
        """添加结构化记忆条目"""
        self._entries.append(entry)
        self._current_tokens += max(1, self._estimate_tokens(entry.content))
        self._gc()

    def get_messages(self, limit: int = 20) -> List[dict]:
        """返回最近消息列表"""
        return self._messages[-limit:]

    def search(self, query: str, top_k: int = 5) -> List[MemorySearchResult]:
        """简单关键词搜索（底座版，不使用向量）"""
        query = query.lower()
        results = []
        for entry in reversed(self._entries):
            if query in entry.content.lower():
                results.append(MemorySearchResult(entry=entry, score=1.0, source="short_term"))
            if len(results) >= top_k:
                break
        return results

    def get_recent(self, limit: int = 10) -> List[MemoryEntry]:
        """返回最近记忆条目"""
        return self._entries[-limit:]

    def clear(self) -> None:
        """清空短期记忆"""
        self._messages.clear()
        self._entries.clear()
        self._current_tokens = 0

    def _gc(self) -> None:
        """按 token 上限做滑动窗口回收"""
        while self._messages and self._current_tokens > self.max_tokens:
            removed = self._messages.pop(0)
            self._current_tokens -= max(1, self._estimate_tokens(removed["content"]))
        while self._entries and self._current_tokens > self.max_tokens:
            removed = self._entries.pop(0)
            self._current_tokens -= max(1, self._estimate_tokens(removed.content))

    def _estimate_tokens(self, text: str) -> int:
        """粗略估算 token 数（1 token ≈ 4 字符）"""
        return max(1, len(text) // 4)

    def __len__(self) -> int:
        return len(self._entries)
