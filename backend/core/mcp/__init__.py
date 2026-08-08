"""
MCP (Model Context Protocol) 服务模块

为 Agent 提供标准化的工具调用协议，支持：
- stdio 传输（本地工具调用）
- SSE 传输（远程工具调用）
- 工具注册与发现
- 请求/响应标准化
"""

from .server import MCPServer
from .tools_adapter import adapt_tool_to_mcp, register_all_tools
from .client import MCPClient
from .transport import SSETransport, StdioTransport

__all__ = [
    "MCPServer",
    "MCPClient",
    "SSETransport",
    "StdioTransport",
    "adapt_tool_to_mcp",
    "register_all_tools",
]
