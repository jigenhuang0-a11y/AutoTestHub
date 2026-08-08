"""
统一工具网关 ToolGateway

提供工具的全生命周期管理：
- ToolRegistry: 多团队隔离的工具注册表
- PermissionManager: 团队级工具白名单
- AuditLogger: 工具调用审计日志
- ToolGateway: 统一入口（注册 + 发现 + 鉴权 + 审计）

设计目标：
1. 新增工具只需注册，编排服务和 Agent 自动可见
2. 每个团队有独立工具命名空间和白名单
3. 所有工具调用全量审计
4. 不打断现有 Django→编排服务的 HTTP 调用链路
"""

from .gateway import ToolGateway, get_tool_gateway
from .registry import ToolRegistry, ToolDef
from .permissions import PermissionManager
from .audit import AuditLogger

__all__ = [
    "ToolGateway",
    "get_tool_gateway",
    "ToolRegistry",
    "ToolDef",
    "PermissionManager",
    "AuditLogger",
]
