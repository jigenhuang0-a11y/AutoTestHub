"""
MemoryManager — 记忆系统总控制器（底座版）

统一管理三层记忆的生命周期：
    ShortTermMemory  → 会话级别，自动 GC
    LongTermMemory   → 跨会话持久化，手动遗忘
    WorkingMemory    → 任务级别，任务结束时释放

核心职责:
    1. 记忆写入：对话后自动提取关键信息存入长期记忆
    2. 记忆检索：ReAct 每轮开始时注入相关历史
    3. 记忆隔离：team_id/user_id 命名空间
    4. 记忆衰减：按重要性 + 时间自动遗忘
"""

import logging
from typing import Optional
from datetime import datetime

from app.core.memory.base import (
    MemoryEntry, MemoryType, MemoryImportance, MemorySearchResult,
)
from app.core.memory.short_term import ShortTermMemory
from app.core.memory.long_term import LongTermMemory
from app.core.memory.working import WorkingMemory
from app.core.memory.retrieval import MemoryRetrieval

logger = logging.getLogger(__name__)


class MemoryManager:
    """
    记忆管理器 — Agent 的"海马体"

    使用方式:
        mm = MemoryManager(team_id="team_a", user_id=1)

        # 写入阶段
        mm.remember("用户偏好 BDD 格式的测试用例", memory_type=MemoryType.PATTERN)

        # 检索阶段（ReAct 每轮开始前）
        context = mm.recall("API 测试相关")

        # 任务结束
        mm.close_task()  # 清理工作记忆，保存有价值信息到长期记忆
    """

    def __init__(
        self,
        team_id: str = "default",
        user_id: int = None,
        embedding_fn=None,
        milvus_host: str = "localhost",
        milvus_port: int = 19530,
        short_term_max_tokens: int = 4000,
    ):
        self.team_id = team_id
        self.user_id = user_id

        # 三层记忆
        self.short_term = ShortTermMemory(max_tokens=short_term_max_tokens)
        self.long_term = LongTermMemory(
            embedding_fn=embedding_fn,
            host=milvus_host,
            port=milvus_port,
        )
        self.working = WorkingMemory()

        # 检索器
        self.retrieval = MemoryRetrieval(
            short_term=self.short_term,
            long_term=self.long_term,
            working=self.working,
        )

        self._task_id: Optional[str] = None

    # ============================================================
    # 写入
    # ============================================================

    def remember(
        self,
        content: str,
        memory_type: MemoryType = MemoryType.FACT,
        importance: MemoryImportance = MemoryImportance.MEDIUM,
        metadata: dict = None,
    ) -> str:
        """主动记住一条信息。存储到长期记忆（Milvus）"""
        self.short_term.add_message(
            "system",
            f"[记忆存储] ({memory_type.value}/{importance.value}) {content}",
        )
        mem_id = self.long_term.store(
            content=content,
            memory_type=memory_type,
            importance=importance,
            team_id=self.team_id,
            user_id=self.user_id,
            task_id=self._task_id,
            metadata=metadata,
        )
        return mem_id

    def auto_extract_and_remember(
        self,
        messages: list[dict],
        llm_fn=None,
    ) -> int:
        """从对话中自动提取关键信息并存储"""
        if not llm_fn or not messages:
            return 0

        extract_prompt = """请从以下对话中提取值得记住的关键信息，每条单独一行。

分类标记:
[FACT] 事实性知识（配置、数据）
[DECISION] 重要决定（为什么选 A 不选 B）
[PATTERN] 用户偏好/行为模式
[LESSON] 经验教训

对话:
"""
        for msg in messages[-6:]:
            extract_prompt += f"[{msg['role']}]: {msg['content'][:300]}\n"

        extract_prompt += "\n请提取（只输出有价值的信息，无意义对话不提取）："

        try:
            extracted = llm_fn(extract_prompt)
            count = 0
            for line in extracted.strip().split("\n"):
                line = line.strip()
                if not line:
                    continue
                mem_type = MemoryType.FACT
                content = line
                for prefix, mtype in [
                    ("[FACT]", MemoryType.FACT),
                    ("[DECISION]", MemoryType.DECISION),
                    ("[PATTERN]", MemoryType.PATTERN),
                    ("[LESSON]", MemoryType.LESSON),
                ]:
                    if line.startswith(prefix):
                        mem_type = mtype
                        content = line[len(prefix):].strip()
                        break
                if content:
                    self.remember(content, memory_type=mem_type)
                    count += 1
            logger.info(f"[Memory] 自动提取 {count} 条记忆")
            return count
        except Exception as e:
            logger.warning(f"[Memory] 自动提取失败: {e}")
            return 0

    # ============================================================
    # 检索
    # ============================================================

    def recall(self, query: str, limit: int = 5) -> str:
        """检索相关记忆并格式化为可注入 LLM 的文本"""
        results = self.retrieval.retrieve(
            query=query,
            team_id=self.team_id,
            limit=limit,
        )

        if not results:
            return ""

        lines = ["## 相关历史记忆"]
        for r in results:
            e = r.entry
            lines.append(
                f"- [{e.memory_type.value} | {e.importance.value}] {e.content[:300]}"
            )
        return "\n".join(lines)

    def get_memory_context(self, query: str = None) -> str:
        """获取完整的记忆上下文（用于 ReAct system prompt）"""
        parts = []

        wm_context = self.working.get_context()
        if wm_context.get("data"):
            parts.append(f"## 当前任务状态\n{wm_context}")

        if query:
            ltm_context = self.recall(query)
            if ltm_context:
                parts.append(ltm_context)

        return "\n\n".join(parts) if parts else ""

    # ============================================================
    # 任务生命周期
    # ============================================================

    def start_task(self, task_id: str) -> None:
        """开始新任务"""
        self._task_id = task_id
        self.working = WorkingMemory(task_id=task_id)
        logger.info(f"[Memory] 任务开始: {task_id}")

    def close_task(self, save_to_long_term: bool = True) -> None:
        """结束任务"""
        if save_to_long_term and self.working.get_all():
            for key, value in self.working.get_all().items():
                if not isinstance(value, str):
                    continue
                if len(value) < 20:
                    continue
                self.remember(
                    f"任务 {self._task_id} 的结果 '{key}': {value[:300]}",
                    memory_type=MemoryType.FACT,
                    importance=MemoryImportance.LOW,
                )
        self.working.clear()
        logger.info(f"[Memory] 任务结束: {self._task_id}")
        self._task_id = None

    # ============================================================
    # 记忆衰减
    # ============================================================

    def prune(self, max_age_days: int = 30) -> int:
        """清理过期记忆"""
        before = (datetime.now().isoformat())[:10]
        count = self.long_term.forget(
            team_id=self.team_id,
            before_date=before,
            min_importance=MemoryImportance.LOW,
        )
        logger.info(f"[Memory] 清理 {count} 条旧记忆 (team={self.team_id})")
        return count

    def health(self) -> dict:
        """健康检查"""
        return {
            "team_id": self.team_id,
            "user_id": self.user_id,
            "task_id": self._task_id,
            "short_term_messages": len(self.short_term.get_messages()),
            "working_memory_keys": len(self.working.get_all()),
            "status": "active",
        }
