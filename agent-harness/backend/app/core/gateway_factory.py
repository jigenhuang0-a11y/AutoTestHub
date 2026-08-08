"""
Gateway 工厂 — 统一创建 ToolGatewayClient + ReActIntegration

解决 ReActAgent 无法自动获取真实 gateway 实例的问题。
提供懒加载单例，确保 ReActAgent 在任何位置都能拿到真实的 ToolGateway。

用法：
    from app.core.gateway_factory import get_tool_gateway_client, get_react_integration

    # 自动创建 ToolGatewayClient（指向 Django MCP API）
    client = get_tool_gateway_client(auth_token="xxx")

    # 自动创建 ReActIntegration（含真实 gateway + router）
    react = get_react_integration(auth_token="xxx")
"""
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

_gateway_client = None
_react_integration = None


def get_tool_gateway_client(
    auth_token: Optional[str] = None,
) -> "ToolGatewayClient":
    """
    获取全局 ToolGatewayClient 单例。

    首次调用时自动创建（指向 Django MCP API），
    后续调用可传入 auth_token 覆盖（不同用户/请求）。

    Args:
        auth_token: Django 认证 Token（透传给 MCP API）
    """
    global _gateway_client
    from app.core.config import DJANGO_MCP_URL
    from app.services.tool_gateway_client import ToolGatewayClient

    if _gateway_client is None:
        _gateway_client = ToolGatewayClient(
            mcp_url=DJANGO_MCP_URL,
            auth_token=auth_token or os.getenv("SERVICE_TOKEN"),
            timeout=120,
        )
        logger.info(
            f"[GatewayFactory] ToolGatewayClient 初始化 → {DJANGO_MCP_URL}"
        )

    # 运行时更新 auth_token（不同用户/请求可能不同）
    if auth_token and _gateway_client.auth_token != auth_token:
        _gateway_client.auth_token = auth_token
        logger.debug("[GatewayFactory] auth_token 已刷新")

    return _gateway_client


def get_react_integration(
    auth_token: Optional[str] = None,
    team_id: str = "default",
    max_iterations: int = 10,
) -> "ReActIntegration":
    """
    获取全局 ReActIntegration 单例（含真实 ToolGatewayClient + LLMRouter）。

    首次调用时自动创建，后续调用可传入 auth_token 覆盖。

    Args:
        auth_token: Django 认证 Token
        team_id: 团队 ID
        max_iterations: ReAct 最大迭代次数
    """
    global _react_integration
    from app.core.react.integration import ReActIntegration
    from app.core.router import get_llm_router

    if _react_integration is None:
        gateway = get_tool_gateway_client(auth_token=auth_token)
        router = get_llm_router()
        _react_integration = ReActIntegration(
            router=router,
            gateway=gateway,
            team_id=team_id,
            max_iterations=max_iterations,
        )
        logger.info(
            f"[GatewayFactory] ReActIntegration 初始化完成 "
            f"(team={team_id}, max_iterations={max_iterations})"
        )

    # 运行时刷新 auth_token
    if auth_token:
        get_tool_gateway_client(auth_token=auth_token)

    return _react_integration


def refresh_auth_token(auth_token: str):
    """运行时刷新所有单例的 auth_token（用户切换场景）"""
    if _gateway_client:
        _gateway_client.auth_token = auth_token
        logger.debug("[GatewayFactory] gateway auth_token 已刷新")
