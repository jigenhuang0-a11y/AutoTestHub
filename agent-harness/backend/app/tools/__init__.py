"""本地工具层：替代原 Django 工具层（agent API / MCP）。

所有工具均为进程内纯函数或轻量类，不依赖任何外部服务（Django 已移除）。
工具通过 ToolRegistry 注册与发现，保留团队命名空间（team_id）能力。
"""
from app.tools.registry import ToolRegistry, get_registry, register_tool

__all__ = ["ToolRegistry", "get_registry", "register_tool"]
