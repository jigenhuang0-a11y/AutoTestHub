"""
工具注册表 — 多团队隔离的工具注册中心

支持：
- 全局工具注册（所有团队可见）
- 团队私有工具注册（仅指定团队可见）
- 工具发现（按 team_id 过滤）
- 工具元数据管理（版本、Schema、Handler）
"""
import logging
from dataclasses import dataclass, field
from typing import Optional, Callable, Any
from threading import Lock

logger = logging.getLogger(__name__)


@dataclass
class ToolDef:
    """工具定义"""
    name: str
    description: str
    input_schema: dict  # JSON Schema
    handler: Callable   # callable(**arguments) -> dict
    category: str = "general"
    version: int = 1
    owner_team_id: Optional[str] = None  # None = 全局工具
    tags: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
            "category": self.category,
            "version": self.version,
            "owner_team_id": self.owner_team_id,
            "tags": self.tags,
        }


class ToolRegistry:
    """
    多团队工具注册表

    注册规则：
    - owner_team_id=None → 全局工具（所有团队可见）
    - owner_team_id="team_a" → 仅 team_a 可见

    示例：
        registry = ToolRegistry()
        registry.register(ToolDef(
            name="testcase_search",
            description="搜索测试用例",
            input_schema={...},
            handler=search_func,
            category="testcase",
        ))
    """

    def __init__(self):
        self._tools: dict[str, ToolDef] = {}  # name → ToolDef
        self._lock = Lock()

    def register(self, tool: ToolDef) -> "ToolRegistry":
        """注册一个工具"""
        with self._lock:
            if tool.name in self._tools:
                existing = self._tools[tool.name]
                tool.version = existing.version + 1
                logger.info(
                    f"[ToolRegistry] 更新工具: {tool.name} v{tool.version} "
                    f"(team={tool.owner_team_id or 'global'})"
                )
            else:
                logger.info(
                    f"[ToolRegistry] 注册工具: {tool.name} "
                    f"(team={tool.owner_team_id or 'global'}, category={tool.category})"
                )
            self._tools[tool.name] = tool
        return self

    def unregister(self, name: str) -> bool:
        """注销工具"""
        with self._lock:
            if name in self._tools:
                del self._tools[name]
                logger.info(f"[ToolRegistry] 注销工具: {name}")
                return True
            return False

    def get(self, name: str) -> Optional[ToolDef]:
        """获取工具定义"""
        return self._tools.get(name)

    def list_tools(self, team_id: Optional[str] = None) -> list[ToolDef]:
        """
        列出工具（按 team 过滤）

        过滤规则：
        - team_id=None → 只返回全局工具
        - team_id="team_a" → 返回全局工具 + team_a 的私有工具
        """
        with self._lock:
            all_tools = list(self._tools.values())

        if team_id is None:
            return [t for t in all_tools if t.owner_team_id is None]

        return [
            t for t in all_tools
            if t.owner_team_id is None or t.owner_team_id == team_id
        ]

    def list_by_category(self, category: str, team_id: Optional[str] = None) -> list[ToolDef]:
        """按分类列出工具"""
        return [t for t in self.list_tools(team_id) if t.category == category]

    def get_categories(self, team_id: Optional[str] = None) -> list[str]:
        """获取所有工具分类"""
        categories = set()
        for t in self.list_tools(team_id):
            categories.add(t.category)
        return sorted(categories)

    def count(self, team_id: Optional[str] = None) -> int:
        """统计工具数量"""
        return len(self.list_tools(team_id))

    def health(self) -> dict:
        """健康检查"""
        return {
            "total_tools": len(self._tools),
            "global_tools": sum(1 for t in self._tools.values() if t.owner_team_id is None),
            "team_tools": sum(1 for t in self._tools.values() if t.owner_team_id is not None),
            "categories": self.get_categories(),
        }
