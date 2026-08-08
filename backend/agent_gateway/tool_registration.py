"""
工具自注册管理器 — Django 启动/工具变更时自动同步到底座

职责：
1. Django 启动时将已注册的 MCP 工具批量推送到编排服务
2. 工具变更（新增/删除/更新）时即时通知底座刷新
3. 提供手动注册的管理命令

架构原则（规范5）：
- 工具定义以 Django 为准（Single Source of Truth）
- 底座作为消费者缓存工具信息
- 双向：底座也能暴露编排能力给 Django 发现
"""
import logging
import os
import time
import threading
from typing import Optional

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

# 编排服务地址
AI_ORCHESTRATION_SERVICE_URL = getattr(
    settings, 'AI_ORCHESTRATION_SERVICE_URL', 'http://localhost:8001'
)

# 重试配置
MAX_RETRIES = getattr(settings, 'TOOL_REGISTRY_MAX_RETRIES', 3)
RETRY_DELAY_BASE = getattr(settings, 'TOOL_REGISTRY_RETRY_DELAY', 2)  # 秒


class ToolRegistrationManager:
    """
    工具注册管理器

    负责将 Django 侧的 MCP 工具定义推送到编排服务底座。

    使用方式：
        manager = ToolRegistrationManager()
        manager.register_to_orchestrator()
    """

    def __init__(self, orchestrator_url: str = None):
        self.orchestrator_url = (orchestrator_url or AI_ORCHESTRATION_SERVICE_URL).rstrip("/")
        self._last_register_time: float = 0
        self._last_register_count: int = 0
        self._lock = threading.Lock()

    # ============================================================
    # 核心注册方法
    # ============================================================

    def register_to_orchestrator(self, team_id: str = None) -> dict:
        """
        将 Django 已注册的所有 MCP 工具批量推送到编排服务

        调用编排服务的 POST /api/v1/tools/register 端点。

        Returns:
            {"registered": N, "updated": N, "failed": N, "errors": [...]}
        """
        tools_data = self._collect_registered_tools()
        if not tools_data:
            logger.info("[ToolReg] 没有需要注册的工具（MCPServer 为空）")
            return {"registered": 0, "updated": 0, "failed": 0, "errors": []}

        payload = {
            "tools": tools_data,
            "django_url": self._get_django_base_url(),
        }

        return self._post_with_retry(
            f"{self.orchestrator_url}/api/v1/tools/register",
            payload,
        )

    def notify_tool_change(self, team_id: str = None) -> dict:
        """
        工具变更后通知底座立即刷新

        调用编排服务的 POST /api/v1/tools/refresh 端点。
        """
        payload = {"force": True}
        if team_id:
            payload["team_id"] = team_id

        return self._post_with_retry(
            f"{self.orchestrator_url}/api/v1/tools/refresh",
            payload,
        )

    def check_orchestrator_status(self) -> dict:
        """
        检查编排服务工具缓存状态

        返回底座当前的工具缓存信息。
        """
        try:
            url = f"{self.orchestrator_url}/api/v1/tools/status"
            resp = requests.get(url, timeout=(3, 10))
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            logger.warning(f"[ToolReg] 查询底座状态失败: {e}")
            return {"error": str(e)}

    def fetch_orchestrator_capabilities(self) -> dict:
        """
        获取底座的编排能力（MCP 元工具列表）

        实现"双向发现"——Django 也能发现底座的编排能力。
        """
        try:
            url = f"{self.orchestrator_url}/api/v1/tools/orchestrator/tools"
            resp = requests.get(url, timeout=(3, 10))
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            logger.warning(f"[ToolReg] 获取底座编排能力失败: {e}")
            return {"tools": [], "error": str(e)}

    # ============================================================
    # 内部方法
    # ============================================================

    def _collect_registered_tools(self) -> list[dict]:
        """
        从 Django MCPServer 收集所有已注册工具

        返回符合底座 ToolRegisterItem schema 的工具列表。
        """
        from core.mcp.server import get_mcp_server

        server = get_mcp_server()
        raw_tools = server.list_tools()

        tools = []
        for t in raw_tools:
            item = {
                "name": t.get("name", ""),
                "description": t.get("description", ""),
                "input_schema": t.get("inputSchema", {}),
                "category": t.get("category", "general"),
                "owner_team_id": t.get("owner_team_id"),
            }
            tools.append(item)

        return tools

    def _get_django_base_url(self) -> str:
        """获取 Django 自身的基础 URL"""
        from django.conf import settings
        # 从 settings 或环境变量获取
        base = getattr(settings, 'BASE_URL', None)
        if base:
            return base.rstrip("/")
        # 回退：从 ALLOWED_HOSTS 推断
        host = getattr(settings, 'ALLOWED_HOSTS', ['localhost'])[0]
        if host in ('*', '0.0.0.0'):
            host = 'localhost'
        port = '8000'  # Django 默认端口
        return f"http://{host}:{port}"

    def _headers(self) -> dict:
        """构建带服务间认证的请求头"""
        svc_token = getattr(settings, 'SERVICE_TOKEN', '') or os.environ.get('SERVICE_TOKEN', '')
        headers = {"Content-Type": "application/json"}
        if svc_token:
            headers["X-Service-Token"] = svc_token
        return headers

    def _post_with_retry(self, url: str, payload: dict) -> dict:
        """
        带重试的 POST 请求

        编排服务启动可能晚于 Django，所以需要重试。
        401/403 不重试（认证错误无法自愈）。
        """
        last_error = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = requests.post(
                    url,
                    json=payload,
                    headers=self._headers(),
                    timeout=(5, 15),
                )
                resp.raise_for_status()
                data = resp.json()
                logger.info(
                    f"[ToolReg] 注册成功 (尝试 {attempt}/{MAX_RETRIES}): "
                    f"registered={data.get('registered', 0)}"
                )
                with self._lock:
                    self._last_register_time = time.time()
                    self._last_register_count = data.get('registered', 0)
                return data

            except requests.ConnectionError as e:
                last_error = e
                if attempt < MAX_RETRIES:
                    delay = RETRY_DELAY_BASE * attempt
                    logger.warning(
                        f"[ToolReg] 连接底座失败 (尝试 {attempt}/{MAX_RETRIES}), "
                        f"{delay}s 后重试: {e}"
                    )
                    time.sleep(delay)
            except requests.HTTPError as e:
                last_error = e
                status = e.response.status_code if e.response is not None else 0
                if status in (401, 403):
                    logger.error(f"[ToolReg] 认证失败 (HTTP {status})，不再重试")
                    break
                logger.warning(
                    f"[ToolReg] HTTP {status} (尝试 {attempt}/{MAX_RETRIES}): {e}"
                )
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY_BASE)
            except requests.RequestException as e:
                last_error = e
                logger.warning(
                    f"[ToolReg] 注册请求失败 (尝试 {attempt}/{MAX_RETRIES}): {e}"
                )
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY_BASE)

        logger.error(f"[ToolReg] 注册失败（已达最大重试 {MAX_RETRIES}）: {last_error}")
        return {"registered": 0, "updated": 0, "failed": 1,
                "errors": [str(last_error)]}


# ============================================================
# 全局单例
# ============================================================

_registration_manager: Optional[ToolRegistrationManager] = None


def get_tool_registration_manager() -> ToolRegistrationManager:
    """获取全局工具注册管理器"""
    global _registration_manager
    if _registration_manager is None:
        _registration_manager = ToolRegistrationManager()
    return _registration_manager


# ============================================================
# 启动注册钩子
# ============================================================

def register_tools_on_startup(team_id: str = None):
    """
    Django 启动时自动注册工具到底座

    应在 AppConfig.ready() 中调用（延迟到子线程避免阻塞启动）。
    """
    def _do_register():
        # 等待 Django 全量加载完成
        time.sleep(2)
        try:
            # 确保工具已注册到本地 MCPServer
            from core.mcp.server import get_mcp_server
            from core.mcp.tools_adapter import register_all_tools

            server = get_mcp_server()
            if server.get_stats()["tools_registered"] == 0:
                count = register_all_tools(server)
                logger.info(f"[ToolReg] 本地注册 {count} 个工具到 MCPServer")

            # 推送到底座
            manager = get_tool_registration_manager()
            result = manager.register_to_orchestrator(team_id=team_id)

            logger.info(
                f"[ToolReg] 启动注册完成: "
                f"registered={result.get('registered', 0)}, "
                f"errors={result.get('errors', [])}"
            )

            # 拉取底座编排能力（双向发现）
            capabilities = manager.fetch_orchestrator_capabilities()
            logger.info(
                f"[ToolReg] 底座编排能力发现: "
                f"{capabilities.get('count', 0)} 个元工具"
            )

        except Exception as e:
            logger.warning(f"[ToolReg] 启动注册异常（非致命）: {e}")

    thread = threading.Thread(target=_do_register, daemon=True, name="tool-reg-startup")
    thread.start()
    return thread
