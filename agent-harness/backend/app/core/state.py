"""
Agent 共享状态定义 (LangGraph State)

编排服务中的状态对象，不依赖 Django 模型。
工作流进度通过 Redis 持久化（多 worker 共享、重启不丢），Redis 不可用时回退内存。
"""
import json
import logging
from typing import Optional, Callable, Any

logger = logging.getLogger(__name__)


class ProgressEvent:
    """工作流进度事件定义"""
    PLAN_START = "plan_start"
    PLAN_COMPLETE = "plan_complete"
    STEP_START = "step_start"
    STEP_PROGRESS = "step_progress"
    STEP_COMPLETE = "step_complete"
    STEP_FAILED = "step_failed"
    VERIFY_START = "verify_start"
    VERIFY_COMPLETE = "verify_complete"
    WORKFLOW_COMPLETE = "workflow_complete"
    WORKFLOW_ERROR = "workflow_error"
    HEAL_START = "heal_start"
    HEAL_STRATEGY = "heal_strategy"
    HEAL_PROGRESS = "heal_progress"
    HEAL_SUCCESS = "heal_success"
    HEAL_FAILED = "heal_failed"
    CHECKPOINT_RESUME = "checkpoint_resume"


class WorkflowProgress:
    """
    工作流进度追踪器 — 优先 Redis 持久化，不可用时回退内存。

    Django 端通过 /api/agent/tasks/progress/{task_id}/ 轮询读取。
    面试要点：进度状态是 LangGraph 工作流的"可观测性窗口"，
    Redis 确保了多 worker、页面刷新、重启后状态不丢失。
    """

    _redis_client = None
    _redis_available = None
    _fallback_store: dict = {}
    _key_prefix = "wfp"

    # ----------------------------------------------------------
    # Redis 连接
    # ----------------------------------------------------------
    @classmethod
    def _init_redis(cls):
        if cls._redis_available is not None:
            return cls._redis_available
        try:
            import redis
            url = cls._get_redis_url()
            cls._redis_client = redis.from_url(url)
            cls._redis_client.ping()
            cls._redis_available = True
            logger.info("[WorkflowProgress] Redis 连接成功")
        except Exception as e:
            cls._redis_available = False
            logger.warning(f"[WorkflowProgress] Redis 不可用 ({e})，回退内存存储")
        return cls._redis_available

    @staticmethod
    def _get_redis_url() -> str:
        """从 app.core.config 读取 REDIS_URL 环境变量"""
        try:
            from app.core.config import settings
            return getattr(settings, 'REDIS_URL', 'redis://localhost:6379/1')
        except Exception:
            import os
            return os.getenv('REDIS_URL', 'redis://localhost:6379/1')

    @classmethod
    def _redis_key(cls, task_id) -> str:
        return f"{cls._key_prefix}:{task_id}"

    # ----------------------------------------------------------
    # 公共 API
    # ----------------------------------------------------------
    @classmethod
    def register(cls, task_id: str, plan: list):
        data = {
            "plan": plan,
            "total_steps": len(plan),
            "completed_steps": 0,
            "steps": [
                {"agent": s["agent"], "description": s.get("description", ""), "status": "pending"}
                for s in plan
            ],
            "current_phase": "pending",
            "logs": [],
            "is_complete": False,
            "error": None,
        }
        if cls._init_redis():
            try:
                cls._redis_client.set(
                    cls._redis_key(task_id),
                    json.dumps(data, ensure_ascii=False),
                    ex=3600,
                )
                return
            except Exception as e:
                logger.warning(f"[WorkflowProgress] Redis 写入失败: {e}")
        cls._fallback_store[task_id] = data

    @classmethod
    def update(cls, task_id: str, phase: str, step_index=None,
               status=None, result=None, error=None, log=None):
        data = cls._read(task_id)
        if not data:
            return
        data["current_phase"] = phase
        if log:
            data["logs"].append(log)
        if step_index is not None and 0 <= step_index < len(data["steps"]):
            data["steps"][step_index]["status"] = status or "running"
            if result:
                data["steps"][step_index]["result"] = result
            if error:
                data["steps"][step_index]["error"] = error
            if status in ("completed", "failed"):
                data["completed_steps"] += 1
        if phase == ProgressEvent.WORKFLOW_COMPLETE:
            data["is_complete"] = True
        if phase == ProgressEvent.WORKFLOW_ERROR:
            data["is_complete"] = True
            data["error"] = error
        cls._write(task_id, data)

    @classmethod
    def get(cls, task_id: str) -> dict:
        return cls._read(task_id)

    @classmethod
    def cleanup(cls, task_id: str):
        if cls._init_redis():
            try:
                cls._redis_client.delete(cls._redis_key(task_id))
                return
            except Exception:
                pass
        cls._fallback_store.pop(task_id, None)

    @classmethod
    def health(cls) -> dict:
        return {
            "backend": "redis" if cls._redis_available else "memory",
            "redis_available": bool(cls._redis_available),
            "fallback_keys": len(cls._fallback_store),
        }

    # ----------------------------------------------------------
    # 内部读写
    # ----------------------------------------------------------
    @classmethod
    def _read(cls, task_id) -> dict:
        if cls._init_redis():
            try:
                raw = cls._redis_client.get(cls._redis_key(task_id))
                if raw:
                    return json.loads(raw)
            except Exception as e:
                logger.warning(f"[WorkflowProgress] Redis 读取失败: {e}")
        return cls._fallback_store.get(task_id, {})

    @classmethod
    def _write(cls, task_id, data: dict):
        if cls._init_redis():
            try:
                cls._redis_client.set(
                    cls._redis_key(task_id),
                    json.dumps(data, ensure_ascii=False),
                    ex=3600,
                )
                return
            except Exception as e:
                logger.warning(f"[WorkflowProgress] Redis 写入失败: {e}")
        cls._fallback_store[task_id] = data
