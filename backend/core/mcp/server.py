"""
MCP Server — Model Context Protocol 服务端

支持 Agent 通过标准化协议发现和调用工具。
Phase 5.1: 本地 MCP Server + 工具注册
"""

import json
import logging
from typing import Optional, Callable, Any

logger = logging.getLogger(__name__)


# ============================================================
# MCP 协议类型定义
# ============================================================

class MCPToolDef:
    """工具定义 — 符合 MCP 规范"""
    def __init__(self, name: str, description: str, input_schema: dict,
                 handler: Callable, category: str = "general"):
        self.name = name
        self.description = description
        self.input_schema = input_schema  # JSON Schema
        self.handler = handler
        self.category = category

    def to_dict(self):
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
            "category": self.category,
        }

    def execute(self, arguments: dict) -> dict:
        """执行工具调用"""
        try:
            result = self.handler(**arguments)
            return {
                "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}],
                "isError": False,
            }
        except Exception as e:
            logger.exception(f"[MCP] 工具 {self.name} 执行失败: {e}")
            return {
                "content": [{"type": "text", "text": str(e)}],
                "isError": True,
            }


# ============================================================
# MCP Server 核心
# ============================================================

class MCPServer:
    """
    MCP 协议服务器

    管理工具注册、发现、调用生命周期。
    默认通过 ToolGateway 进行权限检查 + 审计。

    使用示例:
        server = MCPServer()
        server.register_tool("list_testcases", "列出测试用例", schema, handler)
        result = server.call_tool("list_testcases", {"status": "active"}, team_id="team_a")
    """

    def __init__(self, name: str = "AutoTestHub MCP Server", version: str = "1.0.0",
                 gateway=None):
        self.name = name
        self.version = version
        self._tools: dict[str, MCPToolDef] = {}
        self._resources: dict[str, dict] = {}
        self._prompts: dict[str, dict] = {}
        self._stats = {
            "total_calls": 0,
            "error_calls": 0,
            "tools_registered": 0,
        }
        # 延迟导入避免循环引用
        self._gateway = gateway  # 如果未传入，首次调用时懒加载

    # ============================================================
    # 工具注册
    # ============================================================

    def register_tool(self, name: str, description: str, input_schema: dict,
                      handler: Callable, category: str = "general",
                      owner_team_id: str = None) -> "MCPServer":
        """
        注册一个工具

        Args:
            name: 工具名 (kebab-case 推荐)
            description: 工具描述
            input_schema: JSON Schema 参数定义
            handler: 执行函数 callable(**arguments) -> dict
            category: 分类 (testcase/execution/data/report/knowledge)
            owner_team_id: 所属团队（None=全局工具）
        """
        tool = MCPToolDef(name, description, input_schema, handler, category)
        self._tools[name] = tool
        self._stats["tools_registered"] = len(self._tools)

        # 同步到 ToolGateway registry
        try:
            from core.tool_gateway.registry import ToolDef
            gateway = self._get_gateway()
            gateway.register(ToolDef(
                name=name, description=description,
                input_schema=input_schema, handler=handler,
                category=category, owner_team_id=owner_team_id,
            ))
        except Exception:
            pass  # 注册失败不影响 MCPServer 正常运行

        logger.info(f"[MCP] 注册工具: {name} ({category}) team={owner_team_id or 'global'}")
        return self

    def register_resource(self, uri: str, name: str, description: str, mime_type: str = "application/json"):
        """注册资源"""
        self._resources[uri] = {"name": name, "description": description, "mimeType": mime_type}
        return self

    def register_prompt(self, name: str, description: str, template: str, arguments: list = None):
        """注册提示模板"""
        self._prompts[name] = {"description": description, "template": template, "arguments": arguments or []}
        return self

    # ============================================================
    # 工具调用
    # ============================================================

    def list_tools(self) -> list[dict]:
        """列出所有已注册工具 (符合 MCP tools/list)"""
        return [t.to_dict() for t in self._tools.values()]

    def get_tool(self, name: str) -> Optional[MCPToolDef]:
        """获取单个工具"""
        return self._tools.get(name)

    def _get_gateway(self):
        """懒加载 ToolGateway（避免循环导入）"""
        if self._gateway is None:
            from core.tool_gateway.gateway import get_tool_gateway
            self._gateway = get_tool_gateway()
        return self._gateway

    def call_tool(self, name: str, arguments: dict,
                  team_id: str = None, user_id: int = None) -> dict:
        """
        调用工具 (符合 MCP tools/call)

        优先使用 ToolGateway（含权限检查 + 审计），
        如果网关不可用则回退到直接调用本地工具。

        Returns:
            {"content": [...], "isError": bool}
        """
        self._stats["total_calls"] += 1

        gateway = self._get_gateway()
        if gateway and gateway._enabled:
            # 走 ToolGateway：权限 + 审计 + 执行
            result = gateway.call_tool(
                name=name, arguments=arguments,
                team_id=team_id, user_id=user_id,
            )
        else:
            # 回退：直接调用本地工具（向后兼容）
            tool = self._tools.get(name)
            if not tool:
                self._stats["error_calls"] += 1
                return {
                    "content": [{"type": "text", "text": f"工具 '{name}' 未找到"}],
                    "isError": True,
                }
            result = tool.execute(arguments)

        if result.get("isError"):
            self._stats["error_calls"] += 1
        return result

    def get_stats(self) -> dict:
        """获取统计数据"""
        return dict(self._stats)

    # ============================================================
    # MCP 请求处理 (JSON-RPC 风格)
    # ============================================================

    def handle_request(self, method: str, params: dict = None) -> dict:
        """
        处理 MCP 请求

        支持的方法:
        - initialize: 握手
        - tools/list: 列出工具
        - tools/call: 调用工具
        - resources/list: 列出资源
        - prompts/list: 列出提示
        - server/info: 服务器信息
        """
        params = params or {}

        handlers = {
            "initialize": self._handle_initialize,
            "tools/list": lambda _: {"tools": self.list_tools()},
            "tools/call": lambda p: self.call_tool(
                p.get("name", ""), p.get("arguments", {}),
                team_id=p.get("team_id"), user_id=p.get("user_id"),
            ),
            "resources/list": lambda _: {"resources": list(self._resources.values())},
            "prompts/list": lambda _: {"prompts": list(self._prompts.values())},
            "server/info": lambda _: {"name": self.name, "version": self.version, "stats": self.get_stats()},
        }

        handler = handlers.get(method)
        if not handler:
            return {"error": f"不支持的方法: {method}", "code": -32601}

        try:
            return handler(params)
        except Exception as e:
            logger.exception(f"[MCP] 请求处理失败: {method}")
            return {"error": str(e), "code": -32603}

    def _handle_initialize(self, params: dict) -> dict:
        """MCP 初始化握手"""
        return {
            "protocolVersion": "2024-11-05",
            "serverInfo": {
                "name": self.name,
                "version": self.version,
            },
            "capabilities": {
                "tools": {"listChanged": False},
                "resources": {"subscribe": False, "listChanged": False},
                "prompts": {"listChanged": False},
            },
        }

    # ============================================================
    # Agent 友好接口
    # ============================================================

    def get_tools_for_agent(self) -> list[dict]:
        """
        生成适配 Agent (OpenAI Function Calling 格式) 的工具列表
        """
        functions = []
        for tool in self._tools.values():
            functions.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.input_schema,
                },
            })
        return functions

    def execute_agent_tool_call(self, name: str, arguments: dict) -> str:
        """Agent 调用工具，返回文本结果"""
        result = self.call_tool(name, arguments)
        if result.get("isError"):
            return f"[错误] {result['content'][0]['text']}"
        return result["content"][0]["text"]


# ============================================================
# 全局单例
# ============================================================

_default_server: Optional[MCPServer] = None


def get_mcp_server() -> MCPServer:
    """获取全局 MCP Server 单例"""
    global _default_server
    if _default_server is None:
        _default_server = MCPServer()
    return _default_server
