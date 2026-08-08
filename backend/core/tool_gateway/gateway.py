"""
ToolGateway — 统一工具网关入口

整合注册表、权限、审计三大模块，提供一站式工具管理。

工具调用全流程：
    1. 权限检查（PermissionManager.check）
    2. 审计记录开始（AuditLogger.record）
    3. 从注册表获取工具（ToolRegistry.get）
    4. 执行工具（ToolDef.handler）
    5. 审计记录结果
    6. 返回结果
"""
import logging
import uuid
import time
from typing import Optional, Any

from .registry import ToolRegistry, ToolDef
from .permissions import PermissionManager, DefaultPolicy, RiskLevel
from .audit import AuditLogger, audit_logger

logger = logging.getLogger(__name__)


class ToolGateway:
    """
    统一工具网关

    用法：
        gateway = ToolGateway()

        # 注册工具
        gateway.register(ToolDef(
            name="knowledge_search",
            description="知识库搜索",
            input_schema={"type": "object", "properties": {...}},
            handler=search_handler,
            category="knowledge",
        ))

        # 列出工具
        tools = gateway.list_tools(team_id="team_a")

        # 调用工具（含权限+审计）
        result = gateway.call_tool(
            name="knowledge_search",
            arguments={"query": "登录接口"},
            team_id="team_a",
            user_id=1,
        )
    """

    def __init__(
        self,
        default_policy: DefaultPolicy = DefaultPolicy.PERMISSIVE,
        enable_audit: bool = True,
    ):
        self.registry = ToolRegistry()
        self.permissions = PermissionManager(default_policy=default_policy)
        self.audit = AuditLogger(
            max_in_memory=2000,
            log_to_file=enable_audit,
        )
        self._enabled = True

    # ============================================================
    # 工具注册
    # ============================================================

    def register(self, tool: ToolDef) -> "ToolGateway":
        """注册工具"""
        self.registry.register(tool)
        return self

    def register_batch(self, tools: list[ToolDef]) -> "ToolGateway":
        """批量注册工具"""
        for t in tools:
            self.registry.register(t)
        logger.info(f"[ToolGateway] 批量注册 {len(tools)} 个工具")
        return self

    def unregister(self, name: str) -> bool:
        """注销工具"""
        return self.registry.unregister(name)

    # ============================================================
    # 工具发现
    # ============================================================

    def list_tools(self, team_id: Optional[str] = None) -> list[dict]:
        """
        列出团队可见的工具（含权限信息）

        Returns:
            [{"name": "...", "description": "...", "inputSchema": {...},
              "category": "...", "allowed": true/false, "risk_level": "..."}]
        """
        tool_defs = self.registry.list_tools(team_id)
        result = []
        for t in tool_defs:
            perm = self.permissions.check(team_id or "default", t.name)
            item = t.to_dict()
            item["allowed"] = perm["allowed"]
            item["risk_level"] = perm["risk_level"]
            result.append(item)
        return result

    def get_tools_for_agent(self, team_id: Optional[str] = None) -> list[dict]:
        """
        生成 OpenAI Function Calling 格式的工具列表
        """
        tool_defs = self.registry.list_tools(team_id)
        functions = []
        for t in tool_defs:
            perm = self.permissions.check(team_id or "default", t.name)
            if not perm["allowed"]:
                continue
            functions.append({
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.input_schema,
                },
            })
        return functions

    def get_tool_descriptions(self, team_id: Optional[str] = None) -> str:
        """生成工具描述文本（用于 Prompt）"""
        import json
        tools = self.list_tools(team_id)
        lines = ["## 可用工具\n"]
        for t in tools:
            params = json.dumps(
                t.get("inputSchema", {}).get("properties", {}),
                ensure_ascii=False
            )
            allowed = "✓" if t.get("allowed") else "✗ 无权限"
            lines.append(
                f"- **{t['name']}** [{t.get('category', 'general')}] {allowed}: "
                f"{t['description']}"
            )
            if params != "{}":
                lines.append(f"  参数: {params}")
            lines.append("")
        return "\n".join(lines)

    # ============================================================
    # 工具调用（核心：权限 + 审计）
    # ============================================================

    def call_tool(
        self,
        name: str,
        arguments: dict,
        team_id: Optional[str] = None,
        user_id: Optional[int] = None,
        trace_id: Optional[str] = None,
    ) -> dict:
        """
        调用工具（含完整权限检查 + 审计记录）

        Args:
            name: 工具名
            arguments: 参数
            team_id: 团队 ID
            user_id: 用户 ID
            trace_id: 链路追踪 ID

        Returns:
            {"content": [...], "isError": bool, "audit": {...}}
        """
        trace_id = trace_id or str(uuid.uuid4())[:12]
        team = team_id or "default"
        start = time.time()

        # ---------- 1. 权限检查 ----------
        perm = self.permissions.check(team, name)
        if not perm["allowed"]:
            self.audit.record(
                trace_id=trace_id,
                tool_name=name,
                category="unknown",
                risk_level=perm["risk_level"],
                status="denied",
                arguments=arguments,
                team_id=team,
                user_id=user_id,
                error_message=perm["reason"],
            )
            return {
                "content": [{"type": "text", "text": f"权限拒绝: {perm['reason']}"}],
                "isError": True,
                "audit": {"status": "denied", "reason": perm["reason"]},
            }

        # ---------- 2. 获取工具 ----------
        tool = self.registry.get(name)
        if not tool:
            duration_ms = int((time.time() - start) * 1000)
            self.audit.record(
                trace_id=trace_id,
                tool_name=name,
                category="unknown",
                risk_level=perm["risk_level"],
                status="error",
                arguments=arguments,
                team_id=team,
                user_id=user_id,
                error_message=f"工具 '{name}' 未找到",
                duration_ms=duration_ms,
            )
            return {
                "content": [{"type": "text", "text": f"工具 '{name}' 未注册"}],
                "isError": True,
                "audit": {"status": "error", "error": "tool_not_found"},
            }

        # ---------- 3. 执行工具 ----------
        try:
            result = tool.handler(**arguments)
            duration_ms = int((time.time() - start) * 1000)

            # 统一返回格式
            if not isinstance(result, dict):
                result = {"result": str(result)}
            if "status" not in result:
                result["status"] = "success"

            self.audit.record(
                trace_id=trace_id,
                tool_name=name,
                category=tool.category,
                risk_level=perm["risk_level"],
                status="success",
                arguments=arguments,
                team_id=team,
                user_id=user_id,
                duration_ms=duration_ms,
            )

            return {
                "content": [{"type": "text", "text": _serialize_result(result)}],
                "isError": result.get("status") == "error",
                "audit": {
                    "status": "success",
                    "duration_ms": duration_ms,
                    "risk_level": perm["risk_level"],
                },
            }

        except Exception as e:
            duration_ms = int((time.time() - start) * 1000)
            logger.exception(f"[ToolGateway] 工具 {name} 执行异常")

            self.audit.record(
                trace_id=trace_id,
                tool_name=name,
                category=tool.category,
                risk_level=perm["risk_level"],
                status="error",
                arguments=arguments,
                team_id=team,
                user_id=user_id,
                error_message=str(e),
                duration_ms=duration_ms,
            )

            return {
                "content": [{"type": "text", "text": str(e)}],
                "isError": True,
                "audit": {
                    "status": "error",
                    "error": str(e),
                    "duration_ms": duration_ms,
                },
            }

    # ============================================================
    # 权限管理快捷方法
    # ============================================================

    def allow_team_tools(self, team_id: str, tool_names: list[str]):
        """为团队授权工具"""
        self.permissions.allow_tools_batch(team_id, tool_names)

    def deny_team_tool(self, team_id: str, tool_name: str):
        """禁止团队使用某个工具"""
        self.permissions.deny_tool(team_id, tool_name)

    def set_tool_risk(self, tool_name: str, risk_level: RiskLevel,
                      require_confirmation: bool = False):
        """设置工具风险等级"""
        self.permissions.set_tool_risk(tool_name, risk_level, require_confirmation)

    # ============================================================
    # 管理与健康检查
    # ============================================================

    def get_audit_records(self, team_id: str = None, tool_name: str = None,
                          limit: int = 100) -> list[dict]:
        """查询审计记录"""
        return self.audit.get_records(team_id=team_id, tool_name=tool_name, limit=limit)

    def get_audit_stats(self, team_id: str = None) -> dict:
        """审计统计"""
        return self.audit.stats(team_id=team_id)

    def health(self) -> dict:
        """健康检查"""
        return {
            "enabled": self._enabled,
            "registry": self.registry.health(),
            "permissions": self.permissions.health(),
            "audit": self.audit.health(),
        }

    def disable(self):
        """停用网关（紧急情况）"""
        self._enabled = False
        logger.warning("[ToolGateway] 网关已停用")

    def enable(self):
        """启用网关"""
        self._enabled = True
        logger.info("[ToolGateway] 网关已启用")


def _serialize_result(data: dict) -> str:
    """序列化工具结果为文本"""
    import json
    try:
        # 尝试转为可读 JSON
        return json.dumps(data, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return str(data)


# ============================================================
# 全局单例
# ============================================================

_default_gateway: Optional[ToolGateway] = None


def get_tool_gateway() -> ToolGateway:
    """获取全局 ToolGateway 单例"""
    global _default_gateway
    if _default_gateway is None:
        _default_gateway = ToolGateway()
    return _default_gateway


def reset_tool_gateway():
    """重置全局单例（测试用）"""
    global _default_gateway
    _default_gateway = None
