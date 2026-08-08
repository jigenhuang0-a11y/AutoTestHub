"""
记忆系统模块入口（Django 侧 HTTP 客户端代理）

所有记忆实现已迁至 ai-orchestration-service 底座（FastAPI）。
Django 侧仅保留：
- base.py：纯类型定义（MemoryEntry、MemoryType 等 dataclass）
- client.py：HTTP 客户端，转发到底座 /api/v1/memory/

使用方式（接口兼容）:
    from core.memory import MemoryClient, MemoryType, MemoryImportance

    client = MemoryClient(team_id="team_a", user_id=1)
    client.remember("用户偏好 BDD 格式", memory_type="pattern")
    context = client.recall("测试用例格式")
"""

from core.memory.base import (
    MemoryEntry, MemoryType, MemoryImportance, MemorySearchResult,
)
from core.memory.client import MemoryClient

# 导出 MemoryClient 替代旧的 MemoryManager
__all__ = [
    "MemoryClient",
    "MemoryEntry",
    "MemoryType",
    "MemoryImportance",
    "MemorySearchResult",
]

