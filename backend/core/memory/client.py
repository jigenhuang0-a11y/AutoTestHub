"""
记忆系统 HTTP 客户端 — Django 侧代理

所有记忆操作转发到底座 FastAPI 的 /api/v1/memory/ 端点，
不在 Django 内保留任何记忆实现代码。

使用方式（与原 MemoryManager 接口完全兼容）:
    from core.memory import MemoryClient

    client = MemoryClient(team_id="team_a", user_id=1)
    client.remember("用户偏好 BDD 格式", memory_type="pattern")
    context = client.recall("API 测试相关")
"""

import logging
import os
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# 底座记忆服务地址
MEMORY_SERVICE_URL = os.environ.get(
    "AI_ORCHESTRATION_SERVICE_URL",
    "http://localhost:8001",
)


class MemoryClient:
    """
    底座记忆 HTTP 客户端。

    接口与原 MemoryManager 完全兼容，内部通过 HTTP 调底座。
    """

    def __init__(
        self,
        team_id: str = "default",
        user_id: int = None,
        **kwargs,  # 忽略旧 MemoryManager 参数
    ):
        self.team_id = team_id
        self.user_id = user_id
        self._base_url = MEMORY_SERVICE_URL.rstrip("/") + "/api/v1/memory"
        self._timeout = (3, 10)

    # ============================================================
    # 写入
    # ============================================================

    def remember(
        self,
        content: str,
        memory_type: str = "fact",
        importance: str = "medium",
        metadata: dict = None,
    ) -> str:
        """主动记住一条信息"""
        try:
            resp = requests.post(
                f"{self._base_url}/remember",
                json={
                    "team_id": self.team_id,
                    "user_id": self.user_id,
                    "content": content,
                    "memory_type": str(memory_type),
                    "importance": str(importance),
                    "metadata": metadata,
                },
                timeout=self._timeout,
            )
            resp.raise_for_status()
            return resp.json().get("memory_id", "")
        except requests.RequestException as e:
            logger.warning(f"[MemoryClient] remember 失败: {e}")
            return ""

    # ============================================================
    # 检索
    # ============================================================

    def recall(self, query: str, limit: int = 5) -> str:
        """检索相关记忆"""
        try:
            resp = requests.post(
                f"{self._base_url}/recall",
                json={
                    "team_id": self.team_id,
                    "user_id": self.user_id,
                    "query": query,
                    "limit": limit,
                },
                timeout=self._timeout,
            )
            resp.raise_for_status()
            return resp.json().get("context", "")
        except requests.RequestException as e:
            logger.warning(f"[MemoryClient] recall 失败: {e}")
            return ""

    def get_memory_context(self, query: str = None) -> str:
        """获取完整记忆上下文"""
        try:
            resp = requests.post(
                f"{self._base_url}/context",
                json={
                    "team_id": self.team_id,
                    "user_id": self.user_id,
                    "query": query,
                },
                timeout=self._timeout,
            )
            resp.raise_for_status()
            return resp.json().get("context", "")
        except requests.RequestException as e:
            logger.warning(f"[MemoryClient] get_memory_context 失败: {e}")
            return ""

    # ============================================================
    # 任务生命周期
    # ============================================================

    def start_task(self, task_id: str) -> None:
        """开始新任务"""
        try:
            requests.post(
                f"{self._base_url}/task/start",
                json={
                    "team_id": self.team_id,
                    "user_id": self.user_id,
                    "task_id": task_id,
                },
                timeout=self._timeout,
            ).raise_for_status()
        except requests.RequestException as e:
            logger.warning(f"[MemoryClient] start_task 失败: {e}")

    def close_task(self, save_to_long_term: bool = True) -> None:
        """结束任务"""
        try:
            requests.post(
                f"{self._base_url}/task/close",
                json={
                    "team_id": self.team_id,
                    "user_id": self.user_id,
                    "task_id": "",
                },
                timeout=self._timeout,
            ).raise_for_status()
        except requests.RequestException as e:
            logger.warning(f"[MemoryClient] close_task 失败: {e}")

    # ============================================================
    # 辅助
    # ============================================================

    def health(self) -> dict:
        """健康检查"""
        try:
            resp = requests.get(
                f"{self._base_url}/health",
                timeout=self._timeout,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            return {"status": "unreachable", "error": str(e)}
