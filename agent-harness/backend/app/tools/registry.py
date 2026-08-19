"""本地工具注册表。

替代原 Django MCP 工具发现机制（core/tool_discovery.py）。
工具在进程内注册，支持团队命名空间（team_id），保留"动态发现 + 可插拔"的 SaaS 能力，
但数据源从 Django HTTP 拉取改为本地注册。
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


def _safe_summary(obj: Any, max_len: int = 200) -> str:
    """把任意对象安全转为摘要字符串，用于埋点记录。"""
    try:
        if obj is None:
            return ""
        text = obj if isinstance(obj, str) else str(obj)
        text = text.replace("\n", " ").strip()
        return text[:max_len] + ("..." if len(text) > max_len else "")
    except Exception:
        return "<unserializable>"


@dataclass
class ToolSpec:
    name: str
    description: str
    input_schema: dict
    category: str = "general"
    owner_team_id: Optional[str] = None
    handler: Optional[Callable[..., Any]] = None


class ToolRegistry:
    """进程内工具注册表（单例）。

    与 Django 无关，所有工具在应用启动时由 tools 模块自注册。
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}
        # agent 类型 -> 工具名（用于 Supervisor 决策后的 dispatch 映射）
        self._agent_map: dict[str, str] = {}

    def register(
        self,
        name: str,
        description: str,
        input_schema: dict,
        handler: Callable[..., Any],
        category: str = "general",
        owner_team_id: Optional[str] = None,
        agent_type: Optional[str] = None,
    ) -> None:
        self._tools[name] = ToolSpec(
            name=name,
            description=description,
            input_schema=input_schema,
            category=category,
            owner_team_id=owner_team_id,
            handler=handler,
        )
        if agent_type:
            self._agent_map[agent_type] = name
        logger.debug(f"[ToolRegistry] 注册工具: {name} (category={category})")

    def get(self, name: str) -> Optional[ToolSpec]:
        return self._tools.get(name)

    def list_tools(self, team_id: Optional[str] = None) -> list[ToolSpec]:
        if team_id is None:
            return list(self._tools.values())
        # owner_team_id 为 None 表示平台公共工具，对所有团队可见
        return [
            t
            for t in self._tools.values()
            if t.owner_team_id is None or t.owner_team_id == team_id
        ]

    def call_tool(self, name: str, **kwargs: Any) -> Any:
        spec = self._tools.get(name)
        if spec is None or spec.handler is None:
            raise KeyError(f"工具未注册: {name}")
        # EvalCenter 底座埋点：工具调用开始
        _t0 = time.time()
        try:
            result = spec.handler(**kwargs)
            try:
                from app.core.eval_event_store import record_infra_event

                record_infra_event(
                    feature="tool_call",
                    task_type="tool_call",
                    input_text=f"工具: {name}\n入参: {_safe_summary(kwargs)}",
                    output_text=_safe_summary(result),
                    latency_ms=int((time.time() - _t0) * 1000),
                    model="local",
                    provider="local-registry",
                    metadata={"tool_name": name, "tool_source": "local", "is_mcp": False},
                    status="completed",
                )
            except Exception:
                pass
            return result
        except Exception as e:
            try:
                from app.core.eval_event_store import record_infra_event

                record_infra_event(
                    feature="tool_call",
                    task_type="tool_call",
                    input_text=f"工具: {name}\n入参: {_safe_summary(kwargs)}",
                    output_text=f"ERROR: {e}",
                    latency_ms=int((time.time() - _t0) * 1000),
                    model="local",
                    provider="local-registry",
                    metadata={"tool_name": name, "tool_source": "local", "is_mcp": False, "error": str(e)},
                    status="failed",
                )
            except Exception:
                pass
            raise

    def resolve_agent(self, agent_type: str) -> Optional[str]:
        """Supervisor 决策出 agent 类型后，映射到具体工具名。"""
        return self._agent_map.get(agent_type)

    def health(self) -> dict:
        return {
            "tools_count": len(self._tools),
            "agent_mappings": len(self._agent_map),
            "source": "local",
        }


# 全局单例
_REGISTRY: Optional[ToolRegistry] = None


def get_registry() -> ToolRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = ToolRegistry()
        # 导入工具模块以触发自注册
        from app.tools import testcase_search  # noqa: F401
        from app.tools import testcase_create  # noqa: F401
        from app.tools import data_generate  # noqa: F401
        from app.tools import execution_run  # noqa: F401
        from app.tools import evaluate_run  # noqa: F401
    return _REGISTRY


def register_tool(
    name: str,
    description: str,
    input_schema: dict,
    category: str = "general",
    owner_team_id: Optional[str] = None,
    agent_type: Optional[str] = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """装饰器：将函数注册为工具。"""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        get_registry().register(
            name=name,
            description=description,
            input_schema=input_schema,
            handler=func,
            category=category,
            owner_team_id=owner_team_id,
            agent_type=agent_type,
        )
        return func

    return decorator
