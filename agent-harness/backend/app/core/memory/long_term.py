"""
长期记忆 — 跨会话持久化记忆（SQLite 持久化版）

默认实现：SQLite 持久化（复用 harness.db 的 data 目录），保证重启不丢；
Milvus 未启用时作为兜底，按 team_id + user_id 隔离。

为兼顾语义召回能力：
- 记忆内容 / 元数据持久化到 SQLite（long_term_memories 表）
- embedding 向量在进程内做热缓存（重启后按需要懒重建），召回时优先向量、
  否则降级关键词
"""

import json
import logging
import os
import sqlite3
import threading
import uuid
from datetime import datetime
from typing import List, Optional, Callable
from app.core.memory.base import MemoryEntry, MemorySearchResult, MemoryImportance

logger = logging.getLogger(__name__)

# 与 task_store 共用 data 目录
_DB_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data",
)
_DB_PATH = os.path.join(_DB_DIR, "harness.db")


class LongTermMemory:
    """
    长期记忆存储（SQLite 持久化版）。

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
        db_path: str = _DB_PATH,
    ):
        self.embedding_fn = embedding_fn
        self.host = host
        self.port = port
        self.team_id = team_id
        self.db_path = db_path
        self._lock = threading.RLock()
        # 记忆向量缓存：id -> vector（进程内，重启后懒重建）
        self._vectors: dict[str, List[float]] = {}
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._lock, self._get_conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS long_term_memories (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    memory_type TEXT NOT NULL DEFAULT 'fact',
                    importance TEXT NOT NULL DEFAULT 'medium',
                    team_id TEXT NOT NULL DEFAULT 'default',
                    user_id TEXT,
                    task_id TEXT,
                    metadata TEXT,
                    created_at TEXT,
                    access_count INTEGER DEFAULT 0,
                    last_accessed TEXT
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_ltm_team_user "
                "ON long_term_memories (team_id, user_id)"
            )
            conn.commit()

    def _row_to_entry(self, row: sqlite3.Row) -> MemoryEntry:
        md = row["metadata"]
        try:
            metadata = json.loads(md) if md else {}
        except Exception:
            metadata = {}
        mem_type = row["memory_type"]
        try:
            mtype = MemoryEntry.__dataclass_fields__["memory_type"].type  # noqa
        except Exception:
            mtype = None
        return MemoryEntry(
            id=row["id"],
            content=row["content"],
            memory_type=_coerce_enum(mem_type, MemoryEntry.__dataclass_fields__["memory_type"].default),
            importance=_coerce_enum(row["importance"], MemoryImportance.MEDIUM),
            team_id=row["team_id"],
            user_id=row["user_id"],
            task_id=row["task_id"],
            metadata=metadata,
            created_at=row["created_at"] or datetime.now().isoformat(),
            access_count=row["access_count"] or 0,
            last_accessed=row["last_accessed"],
        )

    def _vectorize(self, content: str) -> Optional[List[float]]:
        if not self.embedding_fn:
            return None
        try:
            return self.embedding_fn([content])[0]
        except Exception as e:
            logger.warning(f"[LongTermMemory] 向量化失败（降级关键词召回）: {e}")
            return None

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
        """持久化存储记忆，返回记忆 ID"""
        entry = MemoryEntry(
            id=str(uuid.uuid4()),
            content=content,
            memory_type=MemoryType_from_str(memory_type),
            importance=importance,
            team_id=team_id or self.team_id,
            user_id=user_id,
            task_id=task_id,
            metadata=metadata or {},
        )
        vec = self._vectorize(content)
        if vec is not None:
            self._vectors[entry.id] = vec
        with self._lock, self._get_conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO long_term_memories
                (id, content, memory_type, importance, team_id, user_id, task_id,
                 metadata, created_at, access_count, last_accessed)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    entry.id, entry.content, entry.memory_type.value,
                    entry.importance.value, entry.team_id,
                    str(entry.user_id) if entry.user_id is not None else None,
                    entry.task_id, json.dumps(entry.metadata, ensure_ascii=False),
                    entry.created_at, entry.access_count, entry.last_accessed,
                ),
            )
            conn.commit()
        return entry.id

    def remember(self, entry: MemoryEntry) -> str:
        """持久化存储 MemoryEntry 对象，返回记忆 ID"""
        if not entry.id:
            entry.id = str(uuid.uuid4())
        entry.team_id = entry.team_id or self.team_id
        vec = self._vectorize(entry.content)
        if vec is not None:
            self._vectors[entry.id] = vec
        with self._lock, self._get_conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO long_term_memories
                (id, content, memory_type, importance, team_id, user_id, task_id,
                 metadata, created_at, access_count, last_accessed)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    entry.id, entry.content, entry.memory_type.value,
                    entry.importance.value, entry.team_id,
                    str(entry.user_id) if entry.user_id is not None else None,
                    entry.task_id, json.dumps(entry.metadata, ensure_ascii=False),
                    entry.created_at, entry.access_count, entry.last_accessed,
                ),
            )
            conn.commit()
        return entry.id

    def _cosine(self, a: List[float], b: List[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        na = sum(x * x for x in a) ** 0.5
        nb = sum(y * y for y in b) ** 0.5
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)

    def _load_entries(self, team_id: str = None) -> List[MemoryEntry]:
        """从 DB 载入候选记忆（按 team 隔离）。"""
        tid = team_id or self.team_id
        with self._lock, self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM long_term_memories WHERE team_id = ? ORDER BY created_at ASC",
                (tid,),
            ).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def recall(self, query: str, top_k: int = 5, threshold: float = 0.0) -> List[MemorySearchResult]:
        """语义向量召回（带关键词兜底），从 DB 读取记忆。"""
        candidates = self._load_entries()
        if not candidates:
            return []

        # 向量语义召回
        if self.embedding_fn:
            q_vec = self._vectorize(query)
            if q_vec is not None:
                scored = []
                for entry in candidates:
                    v = self._vectors.get(entry.id)
                    if v is None:
                        v = self._vectorize(entry.content)
                        if v is not None:
                            self._vectors[entry.id] = v
                    if v is None:
                        continue
                    sim = self._cosine(q_vec, v)
                    if sim >= threshold:
                        scored.append((sim, entry))
                if scored:
                    scored.sort(key=lambda x: x[0], reverse=True)
                    self._touch([e.id for s, e in scored[:top_k]])
                    return [
                        MemorySearchResult(entry=e, score=round(s, 4), source="long_term")
                        for s, e in scored[:top_k]
                    ]

        # 关键词兜底（无 embedding 时）：按字符 n-gram 重叠召回
        q = (query or "").strip().lower()
        results = []
        if q:
            # 生成查询的 2~4 字片段（中文友好）
            ngrams = set()
            for n in (2, 3, 4):
                for i in range(len(q) - n + 1):
                    ngrams.add(q[i:i + n])
            for entry in reversed(candidates):
                content_l = entry.content.lower()
                hit = sum(1 for g in ngrams if g in content_l)
                if hit > 0:
                    score = round(min(1.0, hit / max(1, len(ngrams))), 4)
                    results.append(MemorySearchResult(entry=entry, score=score, source="long_term"))
            results.sort(key=lambda r: r.score, reverse=True)
            results = results[:top_k]
        if results:
            self._touch([r.entry.id for r in results])
        return results

    def _touch(self, ids: List[str]) -> None:
        now = datetime.now().isoformat()
        with self._lock, self._get_conn() as conn:
            for mid in ids:
                conn.execute(
                    "UPDATE long_term_memories SET access_count = access_count + 1, "
                    "last_accessed = ? WHERE id = ?",
                    (now, mid),
                )
            conn.commit()

    def forget(self, memory_id: str = None, team_id: str = None, before_date: str = None, min_importance: MemoryImportance = None) -> int:
        """删除记忆。支持按 ID 删除或按日期/重要性批量清理。"""
        if memory_id:
            with self._lock, self._get_conn() as conn:
                cur = conn.execute("DELETE FROM long_term_memories WHERE id = ?", (memory_id,))
                conn.commit()
                self._vectors.pop(memory_id, None)
                return cur.rowcount
            return 0

        count = 0
        kept_ids = set()
        with self._lock, self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM long_term_memories WHERE team_id = ?",
                (team_id or self.team_id,),
            ).fetchall()
            for r in rows:
                keep = True
                if before_date and (r["created_at"] or "")[:10] >= before_date:
                    keep = False
                if min_importance and (r["importance"] or "") and \
                        _importance_rank(r["importance"]) < _importance_rank(min_importance.value):
                    keep = False
                if keep:
                    kept_ids.add(r["id"])
                else:
                    count += 1
            if count:
                placeholders = ",".join("?" * len(kept_ids)) if kept_ids else ""
                if kept_ids:
                    conn.execute(
                        f"DELETE FROM long_term_memories WHERE team_id = ? AND id NOT IN ({placeholders})",
                        (team_id or self.team_id, *kept_ids),
                    )
                else:
                    conn.execute(
                        "DELETE FROM long_term_memories WHERE team_id = ?",
                        (team_id or self.team_id,),
                    )
                conn.commit()
                for r in rows:
                    if r["id"] not in kept_ids:
                        self._vectors.pop(r["id"], None)
        return count

    def list_all(self, team_id: str = None) -> List[MemoryEntry]:
        """列出所有记忆（按团队隔离；不传则返回全部）"""
        if team_id:
            return self._load_entries(team_id)
        with self._lock, self._get_conn() as conn:
            rows = conn.execute("SELECT * FROM long_term_memories ORDER BY created_at ASC").fetchall()
        return [self._row_to_entry(r) for r in rows]

    def delete(self, memory_id: str) -> bool:
        before = len(self.list_all())
        self.forget(memory_id=memory_id)
        return len(self.list_all()) < before

    def clear(self, team_id: str = None) -> int:
        """清空记忆（按团队或全清），返回清空条数"""
        tid = team_id or self.team_id
        with self._lock, self._get_conn() as conn:
            cur = conn.execute("DELETE FROM long_term_memories WHERE team_id = ?", (tid,))
            conn.commit()
            count = cur.rowcount
        # 清理本进程向量缓存中属于该 team 的条目
        with self._lock:
            for mid in list(self._vectors.keys()):
                self._vectors.pop(mid, None)
        return count

    def decay(self) -> None:
        """记忆衰减（持久化版为空实现，可扩展按 access_count/时间降权）"""
        pass

    def close(self) -> None:
        """关闭（SQLite 连接按需创建，此处无需操作）"""
        pass

    def __len__(self) -> int:
        with self._lock, self._get_conn() as conn:
            cnt = conn.execute(
                "SELECT COUNT(*) AS c FROM long_term_memories WHERE team_id = ?",
                (self.team_id,),
            ).fetchone()["c"]
        return cnt


# ============================================================
# 辅助函数
# ============================================================
def _coerce_enum(value, default):
    from app.core.memory.base import MemoryType, MemoryImportance
    if isinstance(value, (MemoryType, MemoryImportance)):
        return value
    try:
        return type(default)(value)
    except Exception:
        return default


def MemoryType_from_str(value: str):
    from app.core.memory.base import MemoryType
    try:
        return MemoryType(value)
    except Exception:
        return MemoryType.FACT


_IMPORTANCE_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def _importance_rank(value: str) -> int:
    return _IMPORTANCE_ORDER.get(value, 1)
