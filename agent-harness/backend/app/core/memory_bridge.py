"""
memory_bridge — 为 AI 日常对话与 RAG 知识库问答统一接入长短期记忆。

设计目标：
  - 短期记忆（ShortTermMemory）：单会话内的对话上下文，由调用方传入 history 维护。
  - 长期记忆（LongTermMemory，MemoryManager 管理）：跨会话沉淀的用户偏好 / 决策 /
    经验，通过 recall 在生成前注入、通过 auto_extract_and_remember 在回答后沉淀。

使用方式（在 rag.py 的两个入口中）：
    from app.core.memory_bridge import get_memory_for, build_long_term_context, sink_memory

    mm = get_memory_for(user_id, mode="knowledge")
    ltm_ctx = build_long_term_context(mm, question)   # 注入 prompt
    ... 生成回答 ...
    sink_memory(mm, question, answer_text)            # 回答后沉淀
"""

from __future__ import annotations

import logging
from typing import List, Dict, Optional

from app.core.memory import MemoryManager, MemoryType

logger = logging.getLogger(__name__)


# 按 user_id + mode 做进程内实例缓冲，避免每条消息都重建 MemoryManager
_memory_instances: Dict[str, MemoryManager] = {}

# 长期记忆注入上限
LTM_INJECT_LIMIT = 5


def get_memory_for(
    user_id: str,
    mode: str = "chat",
    embedding_fn=None,
) -> MemoryManager:
    """获取（或创建）绑定到 user_id + mode 的记忆管理器。

    mode 用于隔离命名空间：chat（日常对话）/ knowledge（知识库问答）
    长期记忆按 team_id=mode、user_id 隔离，互不污染。
    若 embedding_fn 未显式传入，默认使用全局 embedding 单例（实现语义召回）。
    """
    key = f"{mode}:{user_id}"
    mm = _memory_instances.get(key)
    if mm is None:
        if embedding_fn is None:
            try:
                from app.core.embedding import get_embedding_provider
                embedding_fn = get_embedding_provider().embed
            except Exception as e:
                logger.warning(f"[MemoryBridge] 获取 embedding 失败，降级关键词召回: {e}")
                embedding_fn = None
        mm = MemoryManager(
            team_id=f"memory_{mode}",
            user_id=user_id,
            embedding_fn=embedding_fn,
        )
        _memory_instances[key] = mm
    return mm


def build_long_term_context(mm: MemoryManager, query: str) -> str:
    """根据当前问题检索长期记忆，返回可注入 prompt 的文本块。

    返回空串表示无相关长期记忆。
    """
    if mm is None or not query:
        return ""
    try:
        ctx = mm.recall(query=query, limit=LTM_INJECT_LIMIT)
        if not ctx:
            return ""
        return ctx
    except Exception as e:
        logger.warning(f"[MemoryBridge] recall 失败: {e}")
        return ""


def sink_memory(
    mm: MemoryManager,
    question: str,
    answer: str,
    llm_fn=None,
) -> int:
    """回答完成后，将本轮对话沉淀到长期记忆。

    llm_fn 可选；不传则跳过自动提取（仍可由调用方主动 remember）。
    返回成功沉淀的记忆条数。
    """
    if mm is None:
        return 0
    if not question or not answer:
        return 0
    try:
        messages = [
            {"role": "user", "content": question},
            {"role": "assistant", "content": answer},
        ]
        return mm.auto_extract_and_remember(messages, llm_fn=llm_fn)
    except Exception as e:
        logger.warning(f"[MemoryBridge] 记忆沉淀失败: {e}")
        return 0


def remember_explicit(
    mm: MemoryManager,
    content: str,
    memory_type: MemoryType = MemoryType.FACT,
) -> Optional[str]:
    """主动写入一条长期记忆（供前端显式「记住这点」类操作调用）。"""
    if mm is None or not content:
        return None
    try:
        return mm.remember(content, memory_type=memory_type)
    except Exception as e:
        logger.warning(f"[MemoryBridge] 主动记忆写入失败: {e}")
        return None


def format_long_term_block(ctx: str) -> str:
    """将长期记忆上下文格式化为 prompt 区块。"""
    if not ctx:
        return ""
    return "=== 长期记忆（来自历史对话沉淀） ===\n" + ctx + "\n"


# 支持 mode 枚举，供前端记忆管理面板遍历
ALL_MODES = ["chat", "knowledge"]


def list_memories(user_id: str, mode: Optional[str] = None) -> List[Dict]:
    """列出某用户的长期记忆。

    返回结构：
    [
      {"mode": "chat", "entries": [{"id", "content", "memory_type", "importance", "created_at", "updated_at"}]},
      {"mode": "knowledge", "entries": [...]},
    ]
    若指定 mode 则只返回该 mode。
    """
    modes = [mode] if mode else ALL_MODES
    result: List[Dict] = []
    for m in modes:
        mm = get_memory_for(user_id=user_id, mode=m)
        entries = mm.long_term.list_all() if mm and mm.long_term else []
        result.append({
            "mode": m,
            "entries": [
                {
                    "id": e.id,
                    "content": e.content,
                    "memory_type": e.memory_type.value if hasattr(e.memory_type, "value") else str(e.memory_type),
                    "importance": e.importance.value if hasattr(e.importance, "value") else str(e.importance),
                    "created_at": e.created_at.isoformat() if e.created_at else None,
                    "updated_at": e.updated_at.isoformat() if e.updated_at else None,
                }
                for e in entries
            ],
        })
    return result


def delete_memory(user_id: str, memory_id: str, mode: Optional[str] = None) -> bool:
    """删除一条长期记忆。不指定 mode 时遍历所有 mode 尝试删除。"""
    modes = [mode] if mode else ALL_MODES
    for m in modes:
        mm = get_memory_for(user_id=user_id, mode=m)
        if mm and mm.long_term and mm.long_term.delete(memory_id):
            return True
    return False


def clear_memories(user_id: str, mode: Optional[str] = None) -> int:
    """清空某用户的长期记忆（按 mode 或全清）。返回清空条数。"""
    modes = [mode] if mode else ALL_MODES
    total = 0
    for m in modes:
        mm = get_memory_for(user_id=user_id, mode=m)
        if mm and mm.long_term:
            total += mm.long_term.clear()
    return total
