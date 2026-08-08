"""
工作记忆 — 当前任务的临时状态（底座版）

在任务生命周期内有效的临时上下文，任务结束即释放。

使用场景:
- 当前步骤的部分结果
- 工具调用的中间产物
- 需要跨步骤共享但不需持久化的数据
"""

from typing import Any, Optional


class WorkingMemory:
    """
    任务级工作记忆。

    使用方式:
        wm = WorkingMemory(task_id="task_123")
        wm.set("generated_testcases", [...])
        wm.set("execution_results", {"passed": 10, "failed": 2})
        context = wm.get_context()  # 返回所有工作数据
    """

    def __init__(self, task_id: str = None, ttl_seconds: int = 3600):
        self.task_id = task_id
        self._data: dict[str, Any] = {}
        self._ttl = ttl_seconds

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def delete(self, key: str) -> None:
        self._data.pop(key, None)

    def has(self, key: str) -> bool:
        return key in self._data

    def get_all(self) -> dict[str, Any]:
        return dict(self._data)

    def get_context(self) -> dict:
        """返回适合注入 LLM 上下文的格式"""
        context = {}
        for k, v in self._data.items():
            if isinstance(v, list) and len(v) > 10:
                context[k] = f"[{len(v)} 条数据，前 3 条: {v[:3]}]"
            elif isinstance(v, str) and len(v) > 500:
                context[k] = v[:500] + "..."
            else:
                context[k] = v
        return {
            "task_id": self.task_id,
            "data": context,
        }

    def clear(self) -> None:
        self._data.clear()

    def is_expired(self, current_time: float = None) -> bool:
        """检查是否过期（简化版）"""
        return False
