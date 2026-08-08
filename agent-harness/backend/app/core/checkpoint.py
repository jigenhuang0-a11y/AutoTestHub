"""
Checkpoint 断点续跑存储层

为 LangGraph 工作流提供状态快照持久化：
- 每个节点执行后保存完整 state
- 服务重启后加载最新 checkpoint，从断点继续
- Redis 优先，不可用时回退内存
- 支持版本校验、孤儿清理、重试计数持久化

与 WorkflowProgress 的区别：
- WorkflowProgress：只保存进度/事件，用于前端轮询
- Checkpoint：保存完整 state，用于流程恢复
"""
import json
import logging
import time
from dataclasses import dataclass, asdict
from typing import Optional, Any

logger = logging.getLogger(__name__)

# 当前工作流版本号 — 用于 checkpoint 兼容性校验
# 每次修改工作流结构（新增/删除节点、改变 state schema）时递增
WORKFLOW_CHECKPOINT_VERSION = 2

# 重试上限
MAX_GLOBAL_RETRIES = 3  # 整个工作流最多重试次数
MAX_STEP_RETRIES = 3    # 单步最多重试次数

# 阶段→下一阶段映射（用于自动推断恢复目标）
PHASE_NEXT = {
    "plan": "orchestrate",
    "orchestrate": "verify",
    "verify": "complete",
    "complete": "__end__",
}


@dataclass
class Checkpoint:
    """单个 checkpoint 快照"""
    task_id: str
    phase: str  # plan / orchestrate / verify / complete
    state: dict
    version: int = 1
    created_at: float = 0.0
    # 已完成步骤的 index 列表（用于并行组内恢复）
    completed_steps: Optional[list[int]] = None
    # 每步的重试计数 {step_index: retry_count}
    step_retry_counts: Optional[dict[int, int]] = None
    # 全局重试计数
    retry_count: int = 0

    def __post_init__(self):
        if self.created_at == 0.0:
            self.created_at = time.time()
        if self.completed_steps is None:
            self.completed_steps = []
        if self.step_retry_counts is None:
            self.step_retry_counts = {}

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "phase": self.phase,
            "state": self.state,
            "version": self.version,
            "created_at": self.created_at,
            "completed_steps": self.completed_steps,
            "step_retry_counts": self.step_retry_counts,
            "retry_count": self.retry_count,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Checkpoint":
        return cls(
            task_id=data.get("task_id", ""),
            phase=data.get("phase", ""),
            state=data.get("state", {}),
            version=data.get("version", 1),
            created_at=data.get("created_at", 0.0),
            completed_steps=data.get("completed_steps", []),
            step_retry_counts=data.get("step_retry_counts", {}),
            retry_count=data.get("retry_count", 0),
        )

    def is_compatible(self) -> bool:
        """检查 checkpoint 版本是否与当前工作流兼容"""
        return self.version == WORKFLOW_CHECKPOINT_VERSION

    def next_phase(self) -> str:
        """获取下一个可恢复的阶段"""
        return PHASE_NEXT.get(self.phase, "plan")


class BaseCheckpointStore:
    """Checkpoint 存储接口"""

    def save(self, checkpoint: Checkpoint):
        raise NotImplementedError

    def load(self, task_id: str) -> Optional[Checkpoint]:
        raise NotImplementedError

    def list_history(self, task_id: str, limit: int = 10) -> list[Checkpoint]:
        raise NotImplementedError

    def cleanup(self, task_id: str):
        raise NotImplementedError


class MemoryCheckpointStore(BaseCheckpointStore):
    """内存 Checkpoint 存储（Redis 不可用时的降级）"""

    _store: dict[str, Checkpoint] = {}
    _history: dict[str, list[Checkpoint]] = {}

    def save(self, checkpoint: Checkpoint):
        self._store[checkpoint.task_id] = checkpoint
        self._history.setdefault(checkpoint.task_id, [])
        self._history[checkpoint.task_id].append(checkpoint)
        # 限制历史长度，避免内存无限增长
        if len(self._history[checkpoint.task_id]) > 50:
            self._history[checkpoint.task_id] = self._history[checkpoint.task_id][-50:]
        logger.info(f"[Checkpoint.Memory] 保存 checkpoint: {checkpoint.task_id} phase={checkpoint.phase}")

    def load(self, task_id: str) -> Optional[Checkpoint]:
        return self._store.get(task_id)

    def list_history(self, task_id: str, limit: int = 10) -> list[Checkpoint]:
        return self._history.get(task_id, [])[-limit:]

    def cleanup(self, task_id: str):
        self._store.pop(task_id, None)
        self._history.pop(task_id, None)


class RedisCheckpointStore(BaseCheckpointStore):
    """Redis Checkpoint 存储"""

    KEY_PREFIX = "checkpoint"
    HISTORY_KEY = "checkpoint_history"

    def __init__(self, redis_url: str):
        import redis
        self._redis = redis.from_url(redis_url)
        self._redis.ping()
        logger.info("[Checkpoint.Redis] Redis 连接成功")

    def _latest_key(self, task_id: str) -> str:
        return f"{self.KEY_PREFIX}:latest:{task_id}"

    def _history_key(self, task_id: str) -> str:
        return f"{self.HISTORY_KEY}:{task_id}"

    def save(self, checkpoint: Checkpoint):
        data = json.dumps(checkpoint.to_dict(), ensure_ascii=False)
        # 最新 checkpoint 7 天有效（足够覆盖长流程）
        self._redis.set(self._latest_key(checkpoint.task_id), data, ex=7 * 24 * 3600)
        # 同时写入历史列表，保留最近 50 个
        self._redis.lpush(self._history_key(checkpoint.task_id), data)
        self._redis.ltrim(self._history_key(checkpoint.task_id), 0, 49)
        logger.info(f"[Checkpoint.Redis] 保存 checkpoint: {checkpoint.task_id} phase={checkpoint.phase}")

    def load(self, task_id: str) -> Optional[Checkpoint]:
        raw = self._redis.get(self._latest_key(task_id))
        if not raw:
            return None
        try:
            data = json.loads(raw)
            return Checkpoint.from_dict(data)
        except Exception as e:
            logger.warning(f"[Checkpoint.Redis] 加载 checkpoint 失败: {e}")
            return None

    def list_history(self, task_id: str, limit: int = 10) -> list[Checkpoint]:
        items = self._redis.lrange(self._history_key(task_id), 0, limit - 1)
        checkpoints = []
        for raw in items:
            try:
                data = json.loads(raw)
                checkpoints.append(Checkpoint.from_dict(data))
            except Exception:
                continue
        return checkpoints

    def cleanup(self, task_id: str):
        self._redis.delete(self._latest_key(task_id))
        self._redis.delete(self._history_key(task_id))


# 全局单例（懒加载）
_store_instance: Optional[BaseCheckpointStore] = None
_store_available: Optional[bool] = None


def _get_redis_url() -> str:
    try:
        from app.core.config import settings
        return getattr(settings, 'REDIS_URL', 'redis://localhost:6379/0')
    except Exception:
        import os
        return os.getenv('REDIS_URL', 'redis://localhost:6379/0')


def get_checkpoint_store() -> BaseCheckpointStore:
    """获取全局 CheckpointStore（优先 Redis，失败降级内存）"""
    global _store_instance, _store_available
    if _store_instance is not None:
        return _store_instance
    if _store_available is False:
        return MemoryCheckpointStore()

    try:
        _store_instance = RedisCheckpointStore(_get_redis_url())
        _store_available = True
    except Exception as e:
        logger.warning(f"[Checkpoint] Redis 不可用 ({e})，回退内存存储")
        _store_available = False
        _store_instance = MemoryCheckpointStore()
    return _store_instance


# 非序列化字段黑名单（不能存入 JSON 的字段）
_NON_SERIALIZABLE_FIELDS = {"progress_callback"}


def sanitize_state_for_save(state: dict) -> dict:
    """保存前过滤掉不可序列化的字段"""
    return {k: v for k, v in state.items() if k not in _NON_SERIALIZABLE_FIELDS}


# ============================================================
# Checkpoint 脏/过期判定
# ============================================================

# 超过此时间（秒）未更新的 checkpoint 视为孤儿/过期
ORPHAN_TTL_SECONDS = 24 * 3600  # 24 小时


def is_checkpoint_orphan(checkpoint: Checkpoint, current_time: float = None) -> bool:
    """
    判断 checkpoint 是否为孤儿（工作流已崩溃/超时，不会再恢复）

    判定条件：
    1. phase != "complete"（未正常结束）
    2. 创建时间超过 ORPHAN_TTL_SECONDS
    3. state 中没有正在进行的进度事件
    """
    if checkpoint.phase == "complete":
        return False
    ct = current_time or time.time()
    age = ct - checkpoint.created_at
    return age > ORPHAN_TTL_SECONDS


def save_checkpoint(state: dict, phase: str, completed_steps: list[int] = None,
                    retry_count: int = None):
    """
    在工作流节点中调用，保存当前 state 快照

    Args:
        state: 完整工作流 state
        phase: 当前阶段
        completed_steps: 已完成步骤的 index 列表
        retry_count: 全局重试计数
    """
    task_id = state.get("task_id")
    if not task_id:
        logger.warning("[Checkpoint] 缺少 task_id，无法保存 checkpoint")
        return

    store = get_checkpoint_store()
    clean_state = sanitize_state_for_save(state)

    # 继承已完成步骤列表
    prev = store.load(task_id)
    prev_completed = (prev.completed_steps if prev and prev.completed_steps else [])
    prev_retry_counts = (prev.step_retry_counts if prev and prev.step_retry_counts else {})

    checkpoint = Checkpoint(
        task_id=task_id,
        phase=phase,
        state=clean_state,
        version=WORKFLOW_CHECKPOINT_VERSION,
        completed_steps=completed_steps or prev_completed,
        step_retry_counts=prev_retry_counts,
        retry_count=retry_count if retry_count is not None else (prev.retry_count if prev else 0),
    )
    store.save(checkpoint)


def load_checkpoint(task_id: str, check_version: bool = True) -> Optional[Checkpoint]:
    """
    加载最新 checkpoint

    Args:
        task_id: 任务 ID
        check_version: 是否校验版本兼容性（不兼容时返回 None）

    Returns:
        Checkpoint 或 None
    """
    if not task_id:
        return None
    checkpoint = get_checkpoint_store().load(task_id)
    if checkpoint and check_version and not checkpoint.is_compatible():
        logger.warning(
            f"[Checkpoint] task_id={task_id} 版本不兼容 "
            f"(checkpoint={checkpoint.version}, current={WORKFLOW_CHECKPOINT_VERSION}), 忽略旧 checkpoint"
        )
        return None
    return checkpoint


def cleanup_checkpoint(task_id: str):
    """清理 checkpoint（工作流成功结束后可调用）"""
    if not task_id:
        return
    get_checkpoint_store().cleanup(task_id)


def cleanup_orphan_checkpoints() -> int:
    """
    清理孤儿 checkpoint（启动时或定期调用）

    扫描所有 checkpoint，删除超过 TTL 且未正常结束的。

    Returns:
        清理的 checkpoint 数量
    """
    store = get_checkpoint_store()
    cleaned = 0

    if isinstance(store, RedisCheckpointStore):
        try:
            import redis as _r
            pattern = f"{store.KEY_PREFIX}:latest:*"
            keys = store._redis.keys(pattern)
            current_time = time.time()
            for key in keys:
                raw = store._redis.get(key)
                if not raw:
                    continue
                try:
                    data = json.loads(raw)
                    cp = Checkpoint.from_dict(data)
                    if is_checkpoint_orphan(cp, current_time):
                        task_id = cp.task_id
                        store.cleanup(task_id)
                        cleaned += 1
                        logger.info(f"[Checkpoint] 清理孤儿 checkpoint: {task_id} phase={cp.phase}")
                except Exception:
                    continue
        except Exception as e:
            logger.warning(f"[Checkpoint] 孤儿清理失败: {e}")

    elif isinstance(store, MemoryCheckpointStore):
        current_time = time.time()
        orphan_ids = []
        for task_id, cp in list(store._store.items()):
            if is_checkpoint_orphan(cp, current_time):
                orphan_ids.append(task_id)
        for task_id in orphan_ids:
            store.cleanup(task_id)
            cleaned += 1
            logger.info(f"[Checkpoint] 清理孤儿 checkpoint: {task_id}")

    if cleaned > 0:
        logger.info(f"[Checkpoint] 共清理 {cleaned} 个孤儿 checkpoint")
    return cleaned


def record_step_retry(task_id: str, step_index: int):
    """记录单步重试（持久化到 checkpoint）"""
    store = get_checkpoint_store()
    checkpoint = store.load(task_id)
    if not checkpoint:
        return
    counts = dict(checkpoint.step_retry_counts or {})
    counts[step_index] = counts.get(step_index, 0) + 1
    checkpoint.step_retry_counts = counts
    store.save(checkpoint)
