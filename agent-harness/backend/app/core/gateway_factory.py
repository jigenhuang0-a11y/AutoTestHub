"""
Gateway 工厂 — 统一创建本地工具网关 + ReActIntegration

Django 已彻底移除。原 ToolGatewayClient（指向 Django MCP API）由
LocalToolGateway 替代，内部委托进程内 ToolRegistry（app/tools/registry.py）。

用法：
    from app.core.gateway_factory import get_tool_gateway_client, get_react_integration

    client = get_tool_gateway_client()
    react = get_react_integration(team_id="team_a")
"""
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

_gateway_client = None
_react_integration = None


class LocalToolGateway:
    """本地工具网关适配器。

    兼容 ReAct 层对 gateway 的调用约定（list_tools / call_tool），
    但底层不再走 HTTP，而是直接调用进程内 ToolRegistry。
    """

    def __init__(self, auth_token: Optional[str] = None) -> None:
        from app.tools.registry import get_registry
        self._registry = get_registry()
        self.auth_token = auth_token or os.getenv("SERVICE_TOKEN")

    def list_tools(self, team_id: Optional[str] = None, **kwargs) -> list:
        specs = self._registry.list_tools(team_id=team_id)
        return [
            {
                "name": s.name,
                "description": s.description,
                "inputSchema": s.input_schema,
                "category": s.category,
                "owner_team_id": s.owner_team_id,
            }
            for s in specs
        ]

    def call_tool(
        self,
        name: str,
        arguments: Optional[dict] = None,
        team_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> dict:
        arguments = arguments or {}
        try:
            raw = self._registry.call_tool(name, **arguments)
        except KeyError as e:
            return {"isError": True, "content": [{"type": "text", "text": str(e)}]}
        except Exception as e:  # noqa: BLE001
            logger.error(f"[LocalToolGateway] 工具调用异常 {name}: {e}")
            return {"isError": True, "content": [{"type": "text", "text": str(e)}]}

        if isinstance(raw, dict) and raw.get("status") == "failed":
            return {"isError": True, "content": [{"type": "text", "text": raw.get("error", "执行失败")}]}
        return {
            "isError": False,
            "content": [{"type": "text", "text": _to_text(raw)}],
        }


def _to_text(raw) -> str:
    import json
    if isinstance(raw, dict):
        data = raw.get("data", raw)
    else:
        data = raw
    try:
        return json.dumps(data, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(data)


def get_tool_gateway_client(auth_token: Optional[str] = None) -> "LocalToolGateway":
    """获取全局本地工具网关单例。"""
    global _gateway_client
    if _gateway_client is None:
        _gateway_client = LocalToolGateway(auth_token=auth_token)
        logger.info("[GatewayFactory] LocalToolGateway 初始化完成（替代 Django MCP）")
    if auth_token and _gateway_client.auth_token != auth_token:
        _gateway_client.auth_token = auth_token
    return _gateway_client


def get_react_integration(
    auth_token: Optional[str] = None,
    team_id: str = "default",
    max_iterations: int = 10,
) -> "ReActIntegration":
    """获取全局 ReActIntegration 单例（含本地网关 + LLMRouter）。"""
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
    if auth_token:
        get_tool_gateway_client(auth_token=auth_token)
    return _react_integration


def refresh_auth_token(auth_token: str):
    """运行时刷新所有单例的 auth_token（用户切换场景）"""
    if _gateway_client:
        _gateway_client.auth_token = auth_token
        logger.debug("[GatewayFactory] gateway auth_token 已刷新")
