"""
ToolGateway 客户端 — 编排服务通过 HTTP 调用 Django MCP REST API

替换硬编码的 AGENT_REGISTRY + DjangoClient.call_agent()，
实现动态工具发现和标准化调用。

用法：
    client = ToolGatewayClient(mcp_url="http://localhost:8000")
    tools = client.list_tools(team_id="team_a")
    result = client.call_tool("knowledge_search", {"query": "登录"}, team_id="team_a")
"""
import logging
from typing import Optional

import requests
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.core.telemetry import get_tracer

logger = logging.getLogger(__name__)
tracer = get_tracer(__name__)


def _mcp_retry():
    """MCP 调用重试策略"""
    return retry(
        reraise=False,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((
            requests.exceptions.RequestException,
            requests.exceptions.Timeout,
            httpx.RequestError,
            httpx.TimeoutException,
        )),
    )


class ToolGatewayClient:
    """
    MCP HTTP 客户端 — 连接 Django 的 MCP REST API

    支持：
    - tools/list: GET /api/mcp/tools/list/?team_id=xxx
    - tools/call: POST /api/mcp/tools/call/
    - server/info: GET /api/mcp/server/info/
    - 工具格式：MCP 标准 + OpenAI Function Calling
    """

    # Django MCP REST API 端点
    # 后端注册的是 /api/mcp/tools/，而非 /api/mcp/tools/list/
    ENDPOINTS = {
        "list_tools": "/api/mcp/tools/",
        "call_tool": "/api/mcp/tools/call/",
        "server_info": "/api/mcp/server/info/",
        "health": "/api/mcp/health/",
    }

    def __init__(self, mcp_url: str, auth_token: Optional[str] = None, timeout: int = 30):
        """
        Args:
            mcp_url: Django 服务地址（如 http://localhost:8000）
            auth_token: 认证 Token（透传 Django 鉴权）
            timeout: 请求超时（秒）
        """
        import logging
        self._logger = logging.getLogger(__name__)
        self.mcp_url = mcp_url.rstrip("/")
        self.auth_token = auth_token
        self.timeout = timeout
        self._logger.info(f"[GatewayClient] init: mcp_url={self.mcp_url}, "
                         f"auth_token={'PRESENT' if auth_token else 'MISSING'} "
                         f"(len={len(auth_token) if auth_token else 0})")

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
            headers["X-Service-Token"] = self.auth_token
            self._logger.info(f"[GatewayClient] _headers: Authorization=Bearer **** "
                            f"(token len={len(self.auth_token)})")
        else:
            self._logger.warning(f"[GatewayClient] _headers: NO auth_token, request will be UNAUTHENTICATED")
        return headers

    def _url(self, endpoint_key: str) -> str:
        return f"{self.mcp_url}{self.ENDPOINTS[endpoint_key]}"

    # ============================================================
    # 工具发现
    # ============================================================

    @_mcp_retry()
    def list_tools(self, team_id: Optional[str] = None,
                   format: Optional[str] = None) -> dict:
        """
        列出可用工具

        Args:
            team_id: 团队 ID
            format: "mcp" 或 "openai"，后端默认为 mcp；当前后端带 format=mcp 参数会 404，因此默认不传

        Returns:
            {"tools": [...], "count": N}
        """
        params = {}
        if format:
            params["format"] = format
        if team_id:
            params["team_id"] = team_id

        with tracer.start_as_current_span("tool_gateway.list_tools") as span:
            span.set_attribute("team_id", team_id or "default")
            span.set_attribute("format", format)
            try:
                resp = requests.get(
                    self._url("list_tools"),
                    headers=self._headers(),
                    params=params,
                    timeout=self.timeout,
                )
                resp.raise_for_status()
                data = resp.json()
                span.set_attribute("tool_count", data.get("count", 0))
                return data
            except Exception as e:
                logger.error(f"[ToolGateway] 获取工具列表失败: {e}")
                return {"tools": [], "count": 0, "error": str(e)}

    def get_tools_for_agent(self, team_id: Optional[str] = None) -> list[dict]:
        """
        获取 OpenAI Function Calling 格式的工具列表
        """
        result = self.list_tools(team_id=team_id, format="openai")
        return result.get("tools", [])

    def get_tool_names(self, team_id: Optional[str] = None) -> list[str]:
        """
        获取工具名列表（用于替换 AGENT_REGISTRY）
        """
        result = self.list_tools(team_id=team_id, format="mcp")
        return [t.get("name", "") for t in result.get("tools", [])]

    # ============================================================
    # 工具调用
    # ============================================================

    @_mcp_retry()
    def call_tool(self, name: str, arguments: dict,
                  team_id: Optional[str] = None,
                  user_id: Optional[int] = None) -> dict:
        """
        调用工具

        Args:
            name: 工具名
            arguments: 参数
            team_id: 团队 ID
            user_id: 用户 ID

        Returns:
            {"content": [...], "isError": bool, "audit": {...}}
        """
        payload = {
            "name": name,
            "arguments": arguments,
        }
        if team_id:
            payload["team_id"] = team_id
        if user_id:
            payload["user_id"] = user_id

        with tracer.start_as_current_span("tool_gateway.call_tool") as span:
            span.set_attribute("tool_name", name)
            span.set_attribute("team_id", team_id or "default")
            try:
                resp = requests.post(
                    self._url("call_tool"),
                    headers=self._headers(),
                    json=payload,
                    timeout=self.timeout,
                )
                resp.raise_for_status()
                data = resp.json()
                span.set_attribute("is_error", data.get("isError", False))
                return data
            except Exception as e:
                logger.error(f"[ToolGateway] 工具调用 {name} 失败: {e}")
                return {
                    "content": [{"type": "text", "text": str(e)}],
                    "isError": True,
                }

    # ============================================================
    # 异步版本
    # ============================================================

    @_mcp_retry()
    async def list_tools_async(self, team_id: Optional[str] = None,
                               format: str = "mcp") -> dict:
        """异步列出工具"""
        params = {"format": format}
        if team_id:
            params["team_id"] = team_id

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(
                self._url("list_tools"),
                headers=self._headers(),
                params=params,
            )
            resp.raise_for_status()
            return resp.json()

    @_mcp_retry()
    async def call_tool_async(self, name: str, arguments: dict,
                              team_id: Optional[str] = None) -> dict:
        """异步调用工具"""
        payload = {"name": name, "arguments": arguments}
        if team_id:
            payload["team_id"] = team_id

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                self._url("call_tool"),
                headers=self._headers(),
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()

    # ============================================================
    # 健康检查
    # ============================================================

    def health(self) -> dict:
        """检查 MCP 服务健康状态"""
        try:
            resp = requests.get(
                self._url("health"),
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"[ToolGateway] 健康检查失败: {e}")
            return {"status": "unreachable", "error": str(e)}

    def server_info(self) -> dict:
        """获取 MCP 服务器信息"""
        try:
            resp = requests.get(
                self._url("server_info"),
                headers=self._headers(),
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"[ToolGateway] 获取服务器信息失败: {e}")
            return {"error": str(e)}
