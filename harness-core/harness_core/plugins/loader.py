"""插件动态加载器（P2）。

扫描 harness_plugins 包下所有子模块，自动 import 触发 @register_plugin 注册。
支持白名单/黑名单（P2 先全量加载，P3 接数据库配置动态启停）。
"""
from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path

from harness_core.logging import logger
from harness_core.plugins import list_plugins

# harness_plugins 包根目录（与 harness_core 同级，位于仓库根）
# 本文件: <repo>/harness-core/harness_core/plugins/loader.py -> parents[3] = <repo>
_PLUGINS_ROOT = Path(__file__).resolve().parents[3] / "harness_plugins"


def discover_and_load() -> list[str]:
    """发现并加载所有插件，返回加载到的插件 key 列表。"""
    if not _PLUGINS_ROOT.exists():
        logger.warning(f"[loader] 插件目录不存在: {_PLUGINS_ROOT}")
        return []

    import sys

    root_str = str(_PLUGINS_ROOT.parent)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)

    loaded: list[str] = []
    for entry in pkgutil.iter_modules([str(_PLUGINS_ROOT)]):
        if not entry.ispkg:
            continue
        mod_name = f"harness_plugins.{entry.name}"
        try:
            importlib.import_module(mod_name)
            loaded.append(mod_name)
        except Exception as e:  # noqa: BLE001
            logger.error(f"[loader] 插件 {mod_name} 加载失败: {e}")
    logger.info(f"[loader] 已加载插件模块: {loaded} | 注册表: {list_plugins()}")
    return loaded
