"""
ToolGateway + MCP 集成测试

测试覆盖：
1. ToolRegistry — 工具注册/发现/多团队隔离
2. PermissionManager — 权限策略/白名单/黑名单/风险等级
3. AuditLogger — 审计记录/脱敏/统计
4. ToolGateway — 统一入口（注册+权限+审计）
5. MCPServer + Gateway 集成 — 工具调用走 Gateway
6. ToolDiscovery — 动态工具发现
"""
import pytest
import json
from unittest.mock import MagicMock, patch

# ============================================================
# 1. ToolRegistry 测试
# ============================================================

class TestToolRegistry:
    """工具注册表测试"""

    @pytest.fixture
    def registry(self):
        from core.tool_gateway.registry import ToolRegistry, ToolDef
        return ToolRegistry(), ToolDef

    def test_register_global_tool(self, registry):
        reg, ToolDef = registry
        tool = ToolDef(
            name="testcase_search", description="搜索",
            input_schema={"type": "object", "properties": {}},
            handler=lambda **kw: {"status": "success"},
            category="testcase",
        )
        reg.register(tool)
        assert reg.count() == 1
        assert reg.count(team_id="team_a") == 1  # 全局工具对所有团队可见

    def test_register_team_private_tool(self, registry):
        reg, ToolDef = registry
        tool = ToolDef(
            name="team_custom_sql", description="团队私有",
            input_schema={}, handler=lambda **kw: {},
            category="custom", owner_team_id="team_a",
        )
        reg.register(tool)
        assert reg.count() == 0  # 全局不可见
        assert reg.count(team_id="team_a") == 1  # team_a 可见
        assert reg.count(team_id="team_b") == 0  # team_b 不可见

    def test_list_by_category(self, registry):
        reg, ToolDef = registry
        reg.register(ToolDef("t1", "t1", {}, lambda: {}, category="testcase"))
        reg.register(ToolDef("t2", "t2", {}, lambda: {}, category="execution"))
        reg.register(ToolDef("t3", "t3", {}, lambda: {}, category="testcase"))
        assert len(reg.list_by_category("testcase")) == 2
        assert len(reg.list_by_category("execution")) == 1
        assert len(reg.list_by_category("unknown")) == 0

    def test_get_categories(self, registry):
        reg, ToolDef = registry
        reg.register(ToolDef("t1", "t1", {}, lambda: {}, category="testcase"))
        reg.register(ToolDef("t2", "t2", {}, lambda: {}, category="execution"))
        assert set(reg.get_categories()) == {"testcase", "execution"}

    def test_unregister(self, registry):
        reg, ToolDef = registry
        tool = ToolDef("t1", "t1", {}, lambda: {}, category="testcase")
        reg.register(tool)
        assert reg.count() == 1
        assert reg.unregister("t1") is True
        assert reg.count() == 0
        assert reg.unregister("nonexistent") is False

    def test_version_increment(self, registry):
        reg, ToolDef = registry
        t1 = ToolDef("t1", "v1", {}, lambda: {}, version=1)
        t2 = ToolDef("t1", "v2", {}, lambda: {}, version=1)
        reg.register(t1)
        reg.register(t2)
        assert reg.get("t1").version == 2  # 自动递增


# ============================================================
# 2. PermissionManager 测试
# ============================================================

class TestPermissionManager:
    """权限管理器测试"""

    @pytest.fixture
    def pm(self):
        from core.tool_gateway.permissions import PermissionManager, DefaultPolicy
        return PermissionManager(default_policy=DefaultPolicy.PERMISSIVE)

    def test_permissive_default(self, pm):
        """Permissive 策略下默认允许"""
        result = pm.check("team_a", "knowledge_search")
        assert result["allowed"] is True

    def test_blacklist_blocks(self, pm):
        pm.deny_tool("team_a", "knowledge_search")
        result = pm.check("team_a", "knowledge_search")
        assert result["allowed"] is False
        assert "黑名单" in result["reason"]

    def test_restrictive_requires_whitelist(self, pm):
        from core.tool_gateway.permissions import DefaultPolicy
        pm.default_policy = DefaultPolicy.RESTRICTIVE
        assert pm.check("team_b", "knowledge_search")["allowed"] is False
        pm.allow_tool("team_b", "knowledge_search")
        assert pm.check("team_b", "knowledge_search")["allowed"] is True

    def test_risk_level_defaults(self, pm):
        assert pm.get_risk_level("testcase_search") == "low"
        assert pm.get_risk_level("execution_run") == "high"
        assert pm.get_risk_level("unknown_tool") == "medium"

    def test_set_custom_risk(self, pm):
        from core.tool_gateway.permissions import RiskLevel
        pm.set_tool_risk("execution_run", RiskLevel.CRITICAL, require_confirmation=True)
        result = pm.check("team_a", "execution_run")
        assert result["risk_level"] == "critical"
        assert result["require_confirmation"] is True

    def test_batch_whitelist(self, pm):
        from core.tool_gateway.permissions import DefaultPolicy
        pm.default_policy = DefaultPolicy.RESTRICTIVE
        pm.allow_tools_batch("team_a", ["testcase_search", "knowledge_search", "data_generate"])
        assert pm.check("team_a", "testcase_search")["allowed"] is True
        assert pm.check("team_a", "knowledge_search")["allowed"] is True
        assert pm.check("team_a", "data_generate")["allowed"] is True
        assert pm.check("team_a", "execution_run")["allowed"] is False


# ============================================================
# 3. AuditLogger 测试
# ============================================================

class TestAuditLogger:
    """审计日志测试"""

    @pytest.fixture
    def audit(self):
        from core.tool_gateway.audit import AuditLogger
        return AuditLogger(max_in_memory=100, log_to_file=False)

    def test_record_basic(self, audit):
        record = audit.record(
            trace_id="test-123", tool_name="knowledge_search",
            category="knowledge", risk_level="low",
            status="success", team_id="team_a", user_id=1,
            arguments={"query": "登录接口"},
            duration_ms=150,
        )
        assert record.tool_name == "knowledge_search"
        assert record.status == "success"
        assert len(audit._records) == 1

    def test_sanitize_arguments(self, audit):
        record = audit.record(
            trace_id="test-456", tool_name="api_call",
            category="general", risk_level="medium",
            status="success",
            arguments={"password": "secret123", "token": "abc", "query": "hello"},
            duration_ms=20,
        )
        assert record.arguments["password"] == "***REDACTED***"
        assert record.arguments["token"] == "***REDACTED***"
        assert record.arguments["query"] == "hello"

    def test_record_error(self, audit):
        record = audit.record(
            trace_id="err-789", tool_name="execution_run",
            category="execution", risk_level="high",
            status="error",
            arguments={},
            error_message="Connection timeout",
            duration_ms=5000,
        )
        assert record.status == "error"
        assert "Connection timeout" in record.to_log_line()

    def test_record_denied(self, audit):
        audit.record(
            trace_id="deny-001", tool_name="system_health",
            category="system", risk_level="low",
            status="denied", team_id="team_b",
            arguments={}, error_message="在黑名单中",
        )
        records = audit.get_records(team_id="team_b")
        assert len(records) == 1
        assert records[0]["status"] == "denied"

    def test_stats(self, audit):
        audit.record(trace_id="t1", tool_name="a", category="x", risk_level="low",
                     status="success", arguments={}, duration_ms=10)
        audit.record(trace_id="t2", tool_name="a", category="x", risk_level="low",
                     status="success", arguments={}, duration_ms=10)
        audit.record(trace_id="t3", tool_name="b", category="x", risk_level="low",
                     status="error", arguments={}, duration_ms=10,
                     error_message="fail")
        stats = audit.stats()
        assert stats["total"] == 3
        assert stats["success"] == 2
        assert stats["errors"] == 1
        assert stats["by_tool"]["a"] == 2
        assert stats["by_tool"]["b"] == 1

    def test_max_in_memory(self, audit):
        audit._max = 5
        for i in range(10):
            audit.record(trace_id=f"t{i}", tool_name="test",
                         category="test", risk_level="low",
                         status="success", arguments={}, duration_ms=0)
        assert len(audit._records) == 5


# ============================================================
# 4. ToolGateway 集成测试
# ============================================================

class TestToolGateway:
    """ToolGateway 统一入口测试"""

    @pytest.fixture
    def gateway(self):
        from core.tool_gateway.gateway import ToolGateway, reset_tool_gateway
        reset_tool_gateway()
        gw = ToolGateway()
        return gw

    @pytest.fixture
    def register_search_tool(self, gateway):
        from core.tool_gateway.registry import ToolDef
        gateway.register(ToolDef(
            name="knowledge_search", description="搜索知识库",
            input_schema={"type": "object", "properties": {
                "query": {"type": "string"}
            }, "required": ["query"]},
            handler=lambda query="", **kw: {"results": [f"搜索结果: {query}"], "status": "success"},
            category="knowledge",
        ))

    def test_tool_registration_and_discovery(self, gateway, register_search_tool):
        register_search_tool
        tools = gateway.list_tools(team_id="default")
        assert len(tools) == 1
        assert tools[0]["name"] == "knowledge_search"
        assert tools[0]["allowed"] is True

    def test_call_tool_success(self, gateway, register_search_tool):
        register_search_tool
        result = gateway.call_tool(
            name="knowledge_search",
            arguments={"query": "登录接口"},
            team_id="team_a",
            user_id=1,
        )
        assert result["isError"] is False
        assert result["audit"]["status"] == "success"

    def test_call_tool_not_found(self, gateway):
        result = gateway.call_tool(
            name="nonexistent", arguments={},
            team_id="team_a", user_id=1,
        )
        assert result["isError"] is True
        assert "未注册" in result["content"][0]["text"]

    def test_call_tool_permission_denied(self, gateway, register_search_tool):
        register_search_tool
        gateway.deny_team_tool("team_b", "knowledge_search")
        result = gateway.call_tool(
            name="knowledge_search",
            arguments={"query": "test"},
            team_id="team_b",
            user_id=1,
        )
        assert result["isError"] is True
        assert result["audit"]["status"] == "denied"

    def test_get_tools_for_agent(self, gateway, register_search_tool):
        register_search_tool
        tools = gateway.get_tools_for_agent(team_id="default")
        assert len(tools) == 1
        assert tools[0]["type"] == "function"
        assert tools[0]["function"]["name"] == "knowledge_search"

    def test_audit_records(self, gateway, register_search_tool):
        register_search_tool
        gateway.call_tool("knowledge_search", {"query": "a"}, team_id="team_a", user_id=1)
        gateway.call_tool("knowledge_search", {"query": "b"}, team_id="team_a", user_id=1)
        records = gateway.get_audit_records(team_id="team_a")
        assert len(records) == 2

    def test_audit_stats(self, gateway, register_search_tool):
        register_search_tool
        gateway.call_tool("knowledge_search", {"query": "ok"}, team_id="team_a", user_id=1)
        gateway.call_tool("nonexistent_tool", {}, team_id="team_a", user_id=1)
        stats = gateway.get_audit_stats(team_id="team_a")
        assert stats["success"] >= 1
        assert stats["errors"] >= 1

    def test_global_singleton(self):
        from core.tool_gateway.gateway import get_tool_gateway, reset_tool_gateway
        reset_tool_gateway()
        gw1 = get_tool_gateway()
        gw2 = get_tool_gateway()
        assert gw1 is gw2

    def test_health(self, gateway):
        health = gateway.health()
        assert "registry" in health
        assert "permissions" in health
        assert "audit" in health


# ============================================================
# 5. MCPServer + Gateway 集成测试
# ============================================================

class TestMCPServerGateway:
    """MCPServer 通过 ToolGateway 调用工具"""

    @pytest.fixture
    def server(self):
        from core.mcp.server import MCPServer
        from core.tool_gateway.gateway import reset_tool_gateway
        reset_tool_gateway()
        return MCPServer()

    def test_register_tool_syncs_to_gateway(self, server):
        server.register_tool(
            name="test_tool", description="test",
            input_schema={"type": "object", "properties": {}},
            handler=lambda **kw: {"status": "ok"},
            category="test",
        )
        # Gateway 应该有这个工具
        from core.tool_gateway.gateway import get_tool_gateway
        gw = get_tool_gateway()
        tools = gw.list_tools()
        assert any(t["name"] == "test_tool" for t in tools)

    def test_call_tool_via_gateway(self, server):
        server.register_tool(
            name="echo", description="echo",
            input_schema={"type": "object", "properties": {
                "message": {"type": "string"}
            }},
            handler=lambda message="", **kw: {"echo": message, "status": "success"},
            category="test",
        )
        result = server.call_tool("echo", {"message": "hello"}, team_id="team_a")
        assert result["isError"] is False

    def test_call_tool_permission_denied(self, server):
        server.register_tool("secret_tool", "secret", {}, lambda **kw: {}, category="test")
        from core.tool_gateway.gateway import get_tool_gateway
        gw = get_tool_gateway()
        gw.deny_team_tool("team_b", "secret_tool")
        result = server.call_tool("secret_tool", {}, team_id="team_b")
        assert result["isError"] is True
        assert "权限拒绝" in result["content"][0]["text"]


# ============================================================
# 6. ToolDiscovery 测试
# ============================================================

class TestToolDiscovery:
    """动态工具发现测试"""

    @pytest.fixture
    def discovery(self):
        from app.core.tool_discovery import ToolDiscovery
        return ToolDiscovery(mcp_url="http://localhost:8000")

    def test_fallback_when_no_data(self, discovery):
        """未刷新时使用回退映射"""
        assert discovery.resolve_agent("generator") == "testcase_create"
        assert discovery.resolve_agent("data_factory") == "data_generate"
        assert discovery.resolve_agent("execution") == "execution_run"
        assert discovery.resolve_agent("evaluator") == "evaluate_run"

    def test_resolve_unknown_agent(self, discovery):
        assert discovery.resolve_agent("unknown") is None

    def test_is_stale_initially(self, discovery):
        """初始时应该过期（last_refresh=0）"""
        assert discovery.is_stale() is True

    def test_health(self, discovery):
        health = discovery.health()
        assert health["tools_count"] == 0
        assert health["agent_mappings"] == 0

    def test_get_agent_map_fallback(self, discovery):
        agent_map = discovery.get_agent_map()
        assert agent_map["generator"] == "testcase_create"


# ============================================================
# 运行入口
# ============================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
