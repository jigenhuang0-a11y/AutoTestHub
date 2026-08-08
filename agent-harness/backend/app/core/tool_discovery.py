"""
动态工具发现层 — 替换硬编码 AGENT_REGISTRY

通过 ToolGateway Client 从 Django MCP API 动态获取可用工具，
让编排服务自动感知新增/删除的工具，无需修改代码。

用法：
    discovery = ToolDiscovery(mcp_url="http://localhost:8000")
    discovery.refresh(team_id="team_a")
    tools = discovery.get_agent_tools()  # → {"generator": "testcase_create", ...}
"""
import logging
import time
from typing import Optional
from threading import Lock

logger = logging.getLogger(__name__)

# 回退用：硬编码的 Agent→工具名映射（当 MCP 不可用时使用）
FALLBACK_AGENT_TOOLS = {
    "search": "testcase_search",
    "generator": "testcase_create",
    "data_factory": "data_generate",
    "execution": "execution_run",
    "evaluator": "evaluate_run",
}


class ToolDiscovery:
    """
    动态工具发现器

    使用方式：
        discovery = ToolDiscovery(mcp_url="http://localhost:8000")
        discovery.refresh(team_id="team_a")

        # 根据 Agent 名找到对应工具
        tool_name = discovery.resolve_agent("generator")
        # → "testcase_create"

        # 获取所有可用工具
        all_tools = discovery.get_all_tools()
        # → [{"name": "testcase_create", "description": "...", ...}]
    """

    def __init__(self, mcp_url: str, auth_token: Optional[str] = None,
                 refresh_interval: int = 300):
        """
        Args:
            mcp_url: Django MCP API 地址
            auth_token: 认证 Token
            refresh_interval: 工具列表刷新间隔（秒），默认 5 分钟
        """
        self.mcp_url = mcp_url
        self.auth_token = auth_token
        self.refresh_interval = refresh_interval
        self._tools: list[dict] = []
        self._agent_map: dict[str, str] = {}
        self._last_refresh: float = 0
        self._lock = Lock()

    def refresh(self, team_id: Optional[str] = None, auth_token: Optional[str] = None) -> list[dict]:
        """
        刷新工具列表

        从 Django MCP API 获取最新工具列表，并构建 Agent→工具映射。
        支持请求级 auth_token 透传，避免全局单例在并发请求间互相污染。
        """
        if auth_token is not None:
            self.auth_token = auth_token

        with self._lock:
            try:
                from app.services.tool_gateway_client import ToolGatewayClient
                client = ToolGatewayClient(
                    mcp_url=self.mcp_url,
                    auth_token=self.auth_token,
                )
                result = client.list_tools(team_id=team_id)
                self._tools = result.get("tools", [])

                if not self._tools:
                    logger.warning(
                        "[ToolDiscovery] 从 MCP 获取到空工具列表，使用回退映射"
                    )
                    self._agent_map = dict(FALLBACK_AGENT_TOOLS)
                    return self._tools

                # 构建 Agent→工具映射
                self._build_agent_map()
                self._last_refresh = time.time()

                logger.info(
                    f"[ToolDiscovery] 刷新完成: {len(self._tools)} 个工具, "
                    f"{len(self._agent_map)} 个 Agent 映射"
                )
                return self._tools

            except Exception as e:
                logger.warning(
                    f"[ToolDiscovery] 刷新失败: {e}，使用已有映射"
                )
                if not self._agent_map:
                    self._agent_map = dict(FALLBACK_AGENT_TOOLS)
                return self._tools

    def _build_agent_map(self):
        """从工具列表构建 Agent→工具名映射"""
        self._agent_map = {}

        # 匹配规则：工具名包含 Agent 名关键词
        agent_keywords = {
            "search": ["testcase_search"],
            "generator": ["testcase_create", "testcase_batch_save"],
            "data_factory": ["data_generate", "data_query"],
            "execution": ["execution_run", "execution_status"],
            "evaluator": ["evaluate_run", "report_generate"],
        }

        tool_names = {t.get("name", "") for t in self._tools}

        for agent, candidates in agent_keywords.items():
            matched = None
            for candidate in candidates:
                if candidate in tool_names:
                    matched = candidate
                    break
            self._agent_map[agent] = matched or candidates[0]

    def resolve_agent(self, agent_name: str) -> Optional[str]:
        """
        解析 Agent 名为对应的工具名

        Args:
            agent_name: Agent 名（如 "generator"）

        Returns:
            工具名（如 "testcase_create"），未找到则返回 None
        """
        if not self._agent_map:
            # 还没刷新过，使用回退
            return FALLBACK_AGENT_TOOLS.get(agent_name)

        return self._agent_map.get(
            agent_name,
            FALLBACK_AGENT_TOOLS.get(agent_name),  # 回退
        )

    def get_all_tools(self) -> list[dict]:
        """获取所有可用工具列表"""
        if not self._tools:
            return []
        return list(self._tools)

    def get_tool_names(self) -> list[str]:
        """获取所有工具名"""
        return [t.get("name", "") for t in self._tools]

    def get_agent_map(self) -> dict[str, str]:
        """获取完整的 Agent→工具映射"""
        if not self._agent_map:
            return dict(FALLBACK_AGENT_TOOLS)
        return dict(self._agent_map)

    def is_stale(self) -> bool:
        """工具列表是否过期（超过 refresh_interval）"""
        return (time.time() - self._last_refresh) > self.refresh_interval

    def health(self) -> dict:
        """健康检查"""
        return {
            "tools_count": len(self._tools),
            "agent_mappings": len(self._agent_map),
            "last_refresh": self._last_refresh,
            "stale": self.is_stale(),
        }

    # ============================================================
    # 批量注册 + 强制刷新（供 tool_registry 端点使用）
    # ============================================================

    def bulk_register(self, tools: list[dict]) -> dict:
        """
        批量注册/更新工具缓存（推送模式）

        Django 启动时推送工具列表到此方法，跳过 HTTP 轮询。
        与 refresh() 不同：此方法直接写入缓存，不走网络。

        Returns:
            {"registered": N, "updated": N, "errors": [...]}
        """
        registered = 0
        updated = 0
        errors = []

        with self._lock:
            existing_names = {t.get("name"): i for i, t in enumerate(self._tools)}

            for tool in tools:
                name = tool.get("name", "")
                if not name:
                    errors.append("工具缺少 name 字段")
                    continue

                try:
                    if name in existing_names:
                        self._tools[existing_names[name]] = tool
                        updated += 1
                    else:
                        self._tools.append(tool)
                        registered += 1
                except Exception as e:
                    errors.append(f"{name}: {str(e)}")

            self._build_agent_map()
            self._last_refresh = time.time()

        return {
            "registered": registered,
            "updated": updated,
            "errors": errors,
        }

    def force_refresh(self, team_id: Optional[str] = None) -> dict:
        """
        强制刷新（跳过过期检查），用于工具变更后的即时同步

        Returns:
            {"refreshed": bool, "tool_count": N, "agent_mappings": N}
        """
        tools = self.refresh(team_id=team_id)
        return {
            "refreshed": True,
            "tool_count": len(tools),
            "agent_mappings": len(self._agent_map),
        }


# ============================================================
# 全局单例（workflow.py + tool_registry 端点共享同一实例）
# ============================================================

_global_discovery: Optional[ToolDiscovery] = None
_discovery_lock = Lock()


def get_global_discovery() -> ToolDiscovery:
    """
    获取全局 ToolDiscovery 单例

    确保 workflow.py 的懒加载实例与 tool_registry 端点
    共享同一份工具缓存，避免状态不一致。
    """
    global _global_discovery
    if _global_discovery is None:
        with _discovery_lock:
            if _global_discovery is None:
                from app.core.config import DJANGO_MCP_URL, TOOL_DISCOVERY_REFRESH_INTERVAL
                _global_discovery = ToolDiscovery(
                    mcp_url=DJANGO_MCP_URL,
                    refresh_interval=TOOL_DISCOVERY_REFRESH_INTERVAL,
                )
                logger.info("[ToolDiscovery] 全局单例已初始化")
    return _global_discovery
