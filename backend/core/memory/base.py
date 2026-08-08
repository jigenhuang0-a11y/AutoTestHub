"""
记忆系统 — 核心类型与接口

Agent 的三层记忆模型:
    ShortTermMemory  → 当前会话的消息缓冲（token 窗口滑动）
    LongTermMemory   → 向量化持久记忆（Milvus，按 team_id 隔离命名空间）
    WorkingMemory    → 当前任务临时状态（在任务生命周期内有效）
"""

from dataclasses import dataclass, field
from typing import Any, Optional
from enum import Enum
from datetime import datetime


class MemoryType(str, Enum):
    FACT = "fact"              # 事实性知识（如"项目 A 的 API 端口是 8080"）
    DECISION = "decision"      # 历史决策（如"上次选了方案 B 因为 A 太慢"）
    PATTERN = "pattern"        # 行为模式（如"用户的测试用例偏好 BDD 格式"）
    LESSON = "lesson"          # 经验教训（如"knowledge_search 在小数据集上比 Milvus 快"）


class MemoryImportance(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class MemoryEntry:
    """单条记忆"""
    id: str                                    # 唯一 ID
    content: str                               # 记忆内容
    memory_type: MemoryType = MemoryType.FACT
    importance: MemoryImportance = MemoryImportance.MEDIUM
    team_id: str = "default"                   # 团队隔离
    user_id: Optional[int] = None              # 用户隔离（可选）
    task_id: Optional[str] = None              # 关联任务
    metadata: dict = field(default_factory=dict)
    embedding: Optional[list[float]] = None    # 向量（存储时填充）
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    access_count: int = 0
    last_accessed: Optional[str] = None

    def to_storage_dict(self) -> dict:
        """转为存储格式（不含 embedding，由 Milvus 管理）"""
        return {
            "id": self.id,
            "content": self.content,
            "memory_type": self.memory_type.value,
            "importance": self.importance.value,
            "team_id": self.team_id,
            "user_id": self.user_id,
            "task_id": self.task_id,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "access_count": self.access_count,
            "last_accessed": self.last_accessed,
        }


@dataclass
class MemorySearchResult:
    """记忆搜索结果"""
    entry: MemoryEntry
    score: float                               # 相似度分数
    source: str                                # "short_term" | "long_term" | "working"
