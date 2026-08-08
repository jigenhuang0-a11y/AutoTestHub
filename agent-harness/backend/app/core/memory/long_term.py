"""
长期记忆 — 跨会话持久化记忆（底座版）

简化实现：纯内存存储，Milvus 未启用时作为兜底。按 team_id 隔离。
"""

import logging
import uuid
from datetime import datetime
from typing import List, Optional, Callable
from app.core.memory.base import MemoryEntry, MemorySearchResult, MemoryImportance

logger = logging.getLogger(__name__)


class LongTermMemory:
    """
    长期记忆存储（底座版，纯内存实现）。

    使用方式:
        ltm = LongTermMemory(team_id="team_a")
        ltm.store(content="API 端口 8080", memory_type="fact")
        results = ltm.recall("API 端口")
    """

    def __init__(
        self,
        embedding_fn: Optional[Callable] = None,
        host: str = "localhost",
        port: int = 19530,
        team_id: str = "default",
    ):
        self.embedding_fn = embedding_fn
        self.host = host
        self.port = port
        self.team_id = team_id
        self._entries: List[MemoryEntry] = []

    def store(
        self,
        content: str,
        memory_type: str = "fact",
        importance: MemoryImportance = MemoryImportance.MEDIUM,
        team_id: str = None,
        user_id: int = None,
        task_id: str = None,
        metadata: dict = None,
    ) -> str:
        """存储记忆，返回记忆 ID"""
        entry = MemoryEntry(
            id=str(uuid.uuid4()),
            content=content,
            memory_type=memory_type,
            importance=importance,
            team_id=team_id or self.team_id,
            user_id=user_id,
            task_id=task_id,
            metadata=metadata or {},
        )
        self._entries.append(entry)
        return entry.id

    def remember(self, entry: MemoryEntry) -> str:
        """存储 MemoryEntry 对象，返回记忆 ID"""
        if not entry.id:
            entry.id = str(uuid.uuid4())
        entry.team_id = self.team_id
        self._entries.append(entry)
        return entry.id

    def recall(self, query: str, top_k: int = 5) -> List[MemorySearchResult]:
        """简单关键词召回（底座版）"""
        query = query.lower()
        results = []
        for entry in reversed(self._entries):
            if entry.team_id == self.team_id and query in entry.content.lower():
                results.append(MemorySearchResult(entry=entry, score=1.0, source="long_term"))
            if len(results) >= top_k:
                break
        return results

    def forget(self, memory_id: str = None, team_id: str = None, before_date: str = None, min_importance: MemoryImportance = None) -> int:
        """删除记忆。支持按 ID 删除或按日期/重要性批量清理"""
        if memory_id:
            for i, entry in enumerate(self._entries):
                if entry.id == memory_id:
                    self._entries.pop(i)
                    return 1
            return 0

        count = 0
        kept = []
        for entry in self._entries:
            if team_id and entry.team_id != team_id:
                kept.append(entry)
                continue
            if before_date and entry.created_at[:10] >= before_date:
                kept.append(entry)
                continue
            if min_importance and entry.importance.value < min_importance.value:
                kept.append(entry)
                continue
            count += 1
        self._entries = kept
        return count

    def decay(self) -> None:
        """记忆衰减（底座版为空实现）"""
        pass

    def close(self) -> None:
        """关闭连接（底座版为空实现）"""
        pass

    def __len__(self) -> int:
        return len(self._entries)
