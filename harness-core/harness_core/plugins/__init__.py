"""插件抽象接口（P0 先定义，P2 再做动态加载）。

红线：任何业务功能 = 新插件 or 内核增强，禁止在业务代码里写死调度逻辑。
P1 阶段先用硬编码实现单个插件（测试用例生成），P2 抽离动态加载机制。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class PluginContext:
    """插件运行时上下文：由中台内核注入。"""
    tenant_id: int
    agent_id: int
    model: str
    trace_id: str


@dataclass
class PluginResult:
    success: bool
    data: Any = None
    error: str | None = None


class BasePlugin(ABC):
    """所有业务插件的统一基类。"""

    # 插件唯一标识，必须全局唯一
    key: str = ""
    # 人类可读名称
    name: str = ""
    # 是否需要沙箱执行
    sandbox_required: bool = False

    @abstractmethod
    async def execute(self, ctx: PluginContext, payload: dict) -> PluginResult:
        """执行业务逻辑。具体实现由子类完成。"""
        ...


# P0 阶段：插件注册表（内存）。P2 升级为可发现/可热加载。
_REGISTRY: dict[str, type[BasePlugin]] = {}


def register_plugin(plugin_cls: type[BasePlugin]) -> type[BasePlugin]:
    _REGISTRY[plugin_cls.key] = plugin_cls
    return plugin_cls


def get_plugin(key: str) -> type[BasePlugin] | None:
    return _REGISTRY.get(key)


def list_plugins() -> list[str]:
    return list(_REGISTRY.keys())
