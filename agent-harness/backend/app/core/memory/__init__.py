"""
记忆系统模块入口 — 底座核心能力

使用方式:
    from app.core.memory import MemoryManager, MemoryType, MemoryImportance

    mm = MemoryManager(team_id="team_a", user_id=1)
    mm.remember("用户偏好 BDD 格式", memory_type=MemoryType.PATTERN)
    context = mm.recall("测试用例格式")
"""

from app.core.memory.base import (
    MemoryEntry, MemoryType, MemoryImportance, MemorySearchResult,
)
from app.core.memory.short_term import ShortTermMemory
from app.core.memory.long_term import LongTermMemory
from app.core.memory.working import WorkingMemory
from app.core.memory.retrieval import MemoryRetrieval
from app.core.memory.manager import MemoryManager

__all__ = [
    "MemoryManager",
    "MemoryEntry",
    "MemoryType",
    "MemoryImportance",
    "MemorySearchResult",
    "ShortTermMemory",
    "LongTermMemory",
    "WorkingMemory",
    "MemoryRetrieval",
]
