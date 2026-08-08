"""
权限管理器 — 团队级工具白名单

支持：
- 团队工具白名单（允许/拒绝特定工具）
- 默认策略（permissive: 全部允许 / restrictive: 需要显式授权）
- 工具级别粒度控制
- 危险操作标记
"""
import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional
from threading import Lock

logger = logging.getLogger(__name__)


class DefaultPolicy(str, Enum):
    """默认权限策略"""
    PERMISSIVE = "permissive"     # 全部允许，除非在黑名单
    RESTRICTIVE = "restrictive"   # 全部拒绝，除非在白名单


class RiskLevel(str, Enum):
    """工具风险等级"""
    LOW = "low"          # 只读操作
    MEDIUM = "medium"    # 创建/修改数据
    HIGH = "high"        # 执行/删除/系统操作
    CRITICAL = "critical"  # 不可逆操作


@dataclass
class ToolPermission:
    """工具权限配置"""
    tool_name: str
    risk_level: RiskLevel = RiskLevel.MEDIUM
    require_confirmation: bool = False  # 高风险操作是否需要二次确认
    description: str = ""


class PermissionManager:
    """
    团队级工具权限管理

    权限判断流程：
    1. 检查工具风险等级（critical 需要二次确认）
    2. 检查默认策略（permissive/restrictive）
    3. 检查团队白名单/黑名单
    4. 返回允许/拒绝 + 风险信息

    示例：
        pm = PermissionManager(default_policy=DefaultPolicy.PERMISSIVE)
        pm.allow_tool("team_a", "execution_run")
        pm.deny_tool("team_a", "system_health")
        result = pm.check("team_a", "knowledge_search")
    """

    # 默认工具风险等级映射
    DEFAULT_RISK_LEVELS = {
        # 只读类 → 低风险
        "testcase_search": RiskLevel.LOW,
        "execution_status": RiskLevel.LOW,
        "knowledge_search": RiskLevel.LOW,
        "data_query": RiskLevel.LOW,
        "system_health": RiskLevel.LOW,
        # 创建/修改类 → 中风险
        "testcase_create": RiskLevel.MEDIUM,
        "testcase_update": RiskLevel.MEDIUM,
        "testcase_batch_save": RiskLevel.MEDIUM,
        "data_generate": RiskLevel.MEDIUM,
        "knowledge_upload": RiskLevel.MEDIUM,
        "report_generate": RiskLevel.MEDIUM,
        "evaluate_run": RiskLevel.MEDIUM,
        # 执行/删除类 → 高风险
        "testcase_delete": RiskLevel.HIGH,
        "execution_run": RiskLevel.HIGH,
    }

    def __init__(self, default_policy: DefaultPolicy = DefaultPolicy.PERMISSIVE):
        self.default_policy = default_policy
        self._whitelist: dict[str, set[str]] = {}  # team_id → {tool_names}
        self._blacklist: dict[str, set[str]] = {}  # team_id → {tool_names}
        self._tool_permissions: dict[str, ToolPermission] = {}
        self._lock = Lock()

    def allow_tool(self, team_id: str, tool_name: str):
        """将工具加入团队白名单"""
        with self._lock:
            if team_id not in self._whitelist:
                self._whitelist[team_id] = set()
            self._whitelist[team_id].add(tool_name)

    def allow_tools_batch(self, team_id: str, tool_names: list[str]):
        """批量加入白名单"""
        with self._lock:
            if team_id not in self._whitelist:
                self._whitelist[team_id] = set()
            self._whitelist[team_id].update(tool_names)

    def deny_tool(self, team_id: str, tool_name: str):
        """将工具加入团队黑名单"""
        with self._lock:
            if team_id not in self._blacklist:
                self._blacklist[team_id] = set()
            self._blacklist[team_id].add(tool_name)

    def set_tool_risk(self, tool_name: str, risk_level: RiskLevel,
                      require_confirmation: bool = False):
        """设置工具风险等级"""
        permission = ToolPermission(
            tool_name=tool_name,
            risk_level=risk_level,
            require_confirmation=require_confirmation,
        )
        self._tool_permissions[tool_name] = permission

    def get_risk_level(self, tool_name: str) -> RiskLevel:
        """获取工具风险等级"""
        if tool_name in self._tool_permissions:
            return self._tool_permissions[tool_name].risk_level
        return self.DEFAULT_RISK_LEVELS.get(tool_name, RiskLevel.MEDIUM)

    def check(self, team_id: str, tool_name: str) -> dict:
        """
        检查团队是否有权限调用指定工具

        Returns:
            {
                "allowed": bool,
                "reason": str,
                "risk_level": str,
                "require_confirmation": bool,
            }
        """
        risk = self.get_risk_level(tool_name)
        require_confirm = (
            self._tool_permissions.get(tool_name, ToolPermission(tool_name=tool_name))
            .require_confirmation
        )

        # 1. Critical 级别始终允许但要标记确认
        if risk == RiskLevel.CRITICAL:
            return {
                "allowed": True,
                "reason": "高风险操作，建议二次确认",
                "risk_level": risk.value,
                "require_confirmation": True,
            }

        # 2. 检查黑名单（最高优先级）
        if team_id in self._blacklist and tool_name in self._blacklist[team_id]:
            return {
                "allowed": False,
                "reason": f"工具 '{tool_name}' 在团队 '{team_id}' 黑名单中",
                "risk_level": risk.value,
                "require_confirmation": require_confirm,
            }

        # 3. Permissive 策略：默认允许，除非在黑名单
        if self.default_policy == DefaultPolicy.PERMISSIVE:
            return {
                "allowed": True,
                "reason": "permissive 策略默认允许",
                "risk_level": risk.value,
                "require_confirmation": require_confirm,
            }

        # 4. Restrictive 策略：需要白名单显式授权
        if team_id in self._whitelist and tool_name in self._whitelist[team_id]:
            return {
                "allowed": True,
                "reason": f"工具 '{tool_name}' 在团队 '{team_id}' 白名单中",
                "risk_level": risk.value,
                "require_confirmation": require_confirm,
            }

        return {
            "allowed": False,
            "reason": f"工具 '{tool_name}' 未授权给团队 '{team_id}'（restrictive 策略）",
            "risk_level": risk.value,
            "require_confirmation": require_confirm,
        }

    def get_team_whitelist(self, team_id: str) -> list[str]:
        """获取团队白名单"""
        return sorted(self._whitelist.get(team_id, set()))

    def get_team_blacklist(self, team_id: str) -> list[str]:
        """获取团队黑名单"""
        return sorted(self._blacklist.get(team_id, set()))

    def health(self) -> dict:
        """健康检查"""
        return {
            "default_policy": self.default_policy.value,
            "teams_with_whitelist": len(self._whitelist),
            "teams_with_blacklist": len(self._blacklist),
        }
