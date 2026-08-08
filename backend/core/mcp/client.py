"""
MCP Client — Agent 侧 MCP 工具调用客户端

让 Agent 能够通过 MCP 协议调用远程/本地工具
"""

import json
import logging
from typing import Optional, Callable

logger = logging.getLogger(__name__)


class MCPClient:
    """
    MCP 客户端 — Agent 视角的工具调用接口

    使用场景:
    1. 本地模式: 直接连接本地 MCPServer (同进程)
    2. 远程模式: 通过 SSE/stdio 连接远程 MCP Server

    Usage:
        client = MCPClient(server)
        tools = client.get_tools_for_agent()        # → OpenAI FC 格式
        result = client.call_tool("knowledge_search", {"query": "登录接口"})
    """

    def __init__(self, server=None, transport=None):
        """
        Args:
            server: 本地 MCPServer (本地模式)
            transport: 远程传输实例 (远程模式)
        """
        self.server = server
        self.transport = transport
        self._local_tools: dict[str, Callable] = {}

    @property
    def is_remote(self) -> bool:
        return self.transport is not None

    # ============================================================
    # 工具注册（本地模式快捷方式）
    # ============================================================

    def register_function(self, name: str, func: Callable, description: str = "",
                          parameters: dict = None) -> "MCPClient":
        """注册一个普通函数作为工具"""
        self._local_tools[name] = {
            "func": func,
            "description": description,
            "parameters": parameters or {},
        }
        return self

    # ============================================================
    # Agent 接口
    # ============================================================

    def list_tools(self) -> list[dict]:
        """列出所有可用工具"""
        if self.server:
            return self.server.list_tools()

        # 本地工具
        tools = []
        for name, info in self._local_tools.items():
            tools.append({
                "name": name,
                "description": info["description"],
                "inputSchema": {
                    "type": "object",
                    "properties": info["parameters"],
                    "required": list(info["parameters"].keys()),
                },
            })
        return tools

    def get_tools_for_agent(self) -> list[dict]:
        """
        生成 OpenAI Function Calling 格式的工具列表
        """
        functions = []

        # MCP Server 工具
        if self.server:
            functions.extend(self.server.get_tools_for_agent())

        # 本地注册的函数
        for name, info in self._local_tools.items():
            functions.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": info["description"],
                    "parameters": {
                        "type": "object",
                        "properties": info["parameters"],
                        "required": list(info["parameters"].keys()),
                    },
                },
            })

        return functions

    def get_tool_descriptions(self) -> str:
        """生成工具描述的文本形式（用于 Prompt）"""
        lines = ["## 可用工具\n"]
        for tool in self.list_tools():
            params = json.dumps(tool.get("inputSchema", {}).get("properties", {}), ensure_ascii=False)
            lines.append(f"- **{tool['name']}**: {tool['description']}")
            if params != "{}":
                lines.append(f"  参数: {params}")
            lines.append("")
        return "\n".join(lines)

    def call_tool(self, name: str, arguments: dict) -> dict:
        """
        调用工具

        Returns:
            {"content": [...], "isError": bool}
        """
        # 本地 MCP Server
        if self.server:
            return self.server.call_tool(name, arguments)

        # 本地函数
        if name in self._local_tools:
            try:
                result = self._local_tools[name]["func"](**arguments)
                result_str = json.dumps(result, ensure_ascii=False) if not isinstance(result, str) else result
                return {
                    "content": [{"type": "text", "text": result_str}],
                    "isError": False,
                }
            except Exception as e:
                logger.exception(f"[MCP.Client] 本地工具 {name} 执行失败")
                return {
                    "content": [{"type": "text", "text": str(e)}],
                    "isError": True,
                }

        return {
            "content": [{"type": "text", "text": f"工具 '{name}' 未找到"}],
            "isError": True,
        }

    def execute_agent_tool_call(self, name: str, arguments: dict) -> str:
        """Agent 调用工具，返回文本"""
        result = self.call_tool(name, arguments)
        if result.get("isError"):
            return f"[工具错误] {result['content'][0]['text']}"
        return result["content"][0]["text"]


# ============================================================
# 便捷工厂函数
# ============================================================

def create_local_client(user_id: int = None) -> MCPClient:
    """创建本地 MCP 客户端（连接全局 MCP Server）"""
    from .server import get_mcp_server
    from .tools_adapter import register_all_tools

    server = get_mcp_server()

    # 首次注册所有工具
    if server.get_stats()["tools_registered"] == 0:
        register_all_tools(server, user_id=user_id)

    return MCPClient(server=server)
