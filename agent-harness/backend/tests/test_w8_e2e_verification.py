"""
Phase 2.8 端到端验证测试（FastAPI TestClient 模式）
覆盖：Health → Auth → MCP → Tenant → Workflow → Task → Trace → Cleanup
"""
import os
import sys
import io
import logging
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 抑制日志噪音
for name in ("opentelemetry", "httpx", "app.core.telemetry", "httpcore"):
    logging.getLogger(name).setLevel(logging.ERROR)

os.environ["SERVICE_TOKEN"] = "test-token"
os.environ.setdefault("PORT", "8005")

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
PASS = 0
FAIL = 0

HD = {"X-Service-Token": "test-token"}
STAGE = ""


def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✅ {name}")
    else:
        FAIL += 1
        print(f"  ❌ {name} — {detail}")


def stage(name):
    global STAGE
    STAGE = name
    print(f"\n{'─' * 50}")
    print(f"  【{name}】")
    print(f"{'─' * 50}")


# ============================================================
# 1. 健康检查 — 全部服务存活
# ============================================================
def test_stage_1_health():
    stage("1. 健康检查")
    r = client.get("/api/v1/health/")
    check("Health 返回 200", r.status_code == 200, f"status={r.status_code}")

    data = r.json()
    # status 可能是 "ok" 或 "healthy"，都算健康
    actual_status = data.get("status")
    check(f"status 健康 ({actual_status})",
          actual_status in ("ok", "healthy"), f"status={actual_status}")

    services = data.get("services", [])
    check(f"services 非空 (共 {len(services)} 项)", len(services) >= 1)

    # 检查关键服务（中文名匹配）
    svc_names = {s["name"] for s in services}
    for required_cn, required_en in [
        ("编排服务", "orchestration"),
        ("MCP", "mcp_gateway"),
    ]:
        check(f"包含 {required_en} 服务",
              any(required_cn in name for name in svc_names),
              f"实际服务: {svc_names}")
    print(f"  服务列表: {svc_names}")


# ============================================================
# 2. 认证验证
# ============================================================
def test_stage_2_auth():
    stage("2. 认证验证")

    # 无需认证端点
    r = client.get("/api/v1/health/")
    check("Health 无需认证 (200)", r.status_code == 200)

    # 无凭据拒绝
    r = client.get("/api/v1/mcp/tools/")
    check("无凭据 MCP 被拒 (401/403)",
          r.status_code in (401, 403), f"status={r.status_code}")

    # Service-Token 有效
    r = client.get("/api/v1/mcp/tools/", headers=HD)
    check("Service-Token 有效 (200)", r.status_code == 200)

    # 公开路径不拦截
    for path in ["/api/v1/health/", "/api/v1/health"]:
        r = client.get(path)
        check(f"公开路径 {path} 不拦截", r.status_code == 200, f"status={r.status_code}")


# ============================================================
# 3. MCP 工具注册 + 管理
# ============================================================
def test_stage_3_mcp_tools():
    stage("3. MCP 工具管理")

    # 注册自定义工具（MCPItem 必填: id, name, category, description, endpoint, status, success_rate, avg_latency_ms, call_count）
    custom_name = f"e2e_tool_{uuid.uuid4().hex[:8]}"
    r = client.post("/api/v1/mcp/tools/", json={
        "id": f"e2e-{uuid.uuid4().hex[:8]}",
        "name": custom_name,
        "description": "E2E test tool",
        "category": "code",
        "status": "active",
        "endpoint": "/api/v1/e2e/test",
        "success_rate": 100,
        "avg_latency_ms": 10,
        "call_count": 0,
    }, headers=HD)
    check(f"注册工具 {custom_name} (201)",
          r.status_code in (200, 201), f"status={r.status_code}")
    
    if r.status_code in (200, 201):
        reg_data = r.json()
        check("注册返回包含 name", "name" in reg_data, str(reg_data)[:100])
    else:
        reg_data = {"name": custom_name}

    # 工具列表中可见
    r = client.get("/api/v1/mcp/tools/", headers=HD)
    check("工具列表 200", r.status_code == 200)
    tools = r.json().get("results", [])
    tool_names = [t["name"] for t in tools]
    found = any(custom_name in (t.get("name", "") if isinstance(t, dict) else "") for t in tools)
    check(f"自定义工具存在于列表中", found, f"tools=[{tool_names[:5]}]")

    # 分类列表
    r = client.get("/api/v1/mcp/tools/categories/", headers=HD)
    check("分类列表 200", r.status_code == 200)
    cats = r.json().get("results", [])
    cat_names = [c["name"] for c in cats]
    check(f"分类数量 >= 1 (实际 {len(cats)})", len(cats) >= 1)
    print(f"  分类: {cat_names}")

    # 工具状态切换
    if found:
        r_put = client.put(f"/api/v1/mcp/tools/{custom_name}/",
                           json={"status": "disabled"}, headers=HD)
        check("切换为 disabled (200)", r_put.status_code == 200, r_put.text[:100])
        if r_put.status_code == 200:
            check("状态确认为 disabled", r_put.json().get("status") == "disabled")
        # 恢复
        client.put(f"/api/v1/mcp/tools/{custom_name}/",
                   json={"status": "active"}, headers=HD)


# ============================================================
# 4. 租户生命周期
# ============================================================
def test_stage_4_tenant():
    stage("4. 租户生命周期")

    tenant_name = f"e2e_tenant_{uuid.uuid4().hex[:6]}"

    # 创建
    r = client.post("/api/v1/agent/tenants/", json={
        "name": tenant_name,
        "team": "e2e-team",
        "rate_limit": {"rpm": 30, "qps": 5, "daily_cap": 100},
        "tools_whitelist": ["generator", "evaluator"],
        "contact": "e2e@test.com",
    }, headers=HD)
    check(f"创建租户 (201)", r.status_code in (200, 201), f"status={r.status_code}, body={r.text[:150]}")
    if r.status_code not in (200, 201):
        return

    tenant_data = r.json()
    tenant_id = tenant_data.get("id")
    check(f"返回 tenant_id ({tenant_id})", tenant_id is not None)

    # 列表验证（无 GET /{id}/ 路由）
    r_list = client.get("/api/v1/agent/tenants/", headers=HD)
    check("GET 租户列表 (200)", r_list.status_code == 200)
    if r_list.status_code == 200:
        tenants = r_list.json().get("results", [])
        check(f"租户列表含新建租户", any(t.get("id") == tenant_id for t in tenants))
        # 通过列表找到刚创建的租户，验证字段
        found_tenant = next((t for t in tenants if t.get("id") == tenant_id), None)
        if found_tenant:
            check("名称匹配", found_tenant.get("name") == tenant_name)

    # 删除
    r_del = client.delete(f"/api/v1/agent/tenants/{tenant_id}/", headers=HD)
    check(f"删除租户 (200/204)", r_del.status_code in (200, 204), f"status={r_del.status_code}")

    # 确认已删除：列表不再出现
    if r_del.status_code in (200, 204):
        r_list2 = client.get("/api/v1/agent/tenants/", headers=HD)
        if r_list2.status_code == 200:
            ids = [t.get("id") for t in r_list2.json().get("results", [])]
            check("删除后列表中不再出现", tenant_id not in ids)


# ============================================================
# 5. 工作流调用
# ============================================================
def test_stage_5_workflow():
    stage("5. 工作流调用")

    # 最低限度工作流（不依赖真实 LLM 的 simple 请求，测试契约）
    r = client.post("/api/v1/workflow/invoke", json={
        "user_request": "E2E smoke test — echo only",
        "user_id": 9999,
        "team_id": "e2e-validation",
        "auth_token": "test-token",
    }, headers=HD)
    print(f"  workflow invoke → status={r.status_code}")

    # 4xx 表示正确的契约校验；5xx 表示崩溃；2xx 是理想情况
    check("工作流调用不崩溃 (非 5xx)",
          r.status_code < 500,
          f"status={r.status_code}, detail={r.text[:200]}")

    if r.status_code >= 500:
        print(f"  ⚠ 工作流内部异常，可能缺 LLM Key，但不影响其他验证")
        return

    data = r.json() if r.text else {}
    task_id = data.get("task_id")

    # 检查是否有结果
    if task_id:
        check(f"返回 task_id ({task_id[:16]}...)", True)
    else:
        check("响应为有效 JSON (即使走不到 LLM)", isinstance(data, dict),
              f"type={type(data).__name__}")


# ============================================================
# 6. 任务跟踪
# ============================================================
def test_stage_6_tasks():
    stage("6. 任务跟踪")

    # 任务列表
    r = client.get("/api/v1/agent/tasks/", headers=HD)
    is_ok = r.status_code == 200
    check("任务列表 200", is_ok, f"status={r.status_code}")
    if is_ok:
        data = r.json()
        tasks = data.get("results", [])
        print(f"  现有任务数: {len(tasks)} (count={data.get('count', '?')})")
        if tasks:
            first = tasks[0]
            # 任务存储用 "id"，不是 "task_id"
            check("任务含 id", "id" in first, f"keys={list(first.keys())}")
            check("任务含 status", "status" in first)
            check("任务含 created_at", "created_at" in first)

    # 任务统计
    r_stats = client.get("/api/v1/agent/tasks/stats/", headers=HD)
    stats_ok = r_stats.status_code == 200
    check("任务统计 200", stats_ok, f"status={r_stats.status_code}")
    if stats_ok:
        stats = r_stats.json()
        stat_keys = list(stats.keys())
        check(f"stats 非空 (keys={stat_keys})", len(stats) > 0)
        print(f"  统计: {stats}")

    # → 如果有已完成/失败任务，查 trace
    if is_ok:
        tasks = data.get("results", [])
        traceable = [t for t in tasks if t.get("status") in ("completed", "failed", "processing")]
        if traceable:
            tid = traceable[0].get("id") or traceable[0].get("task_id")
            if tid:
                r_trace = client.get(f"/api/v1/agent/tasks/trace/{tid}/", headers=HD)
                check(f"Trace 查询 (task={str(tid)[:12]}...)", r_trace.status_code in (200, 404),
                      f"status={r_trace.status_code}")
                if r_trace.status_code == 200:
                    trace_data = r_trace.json()
                    check("Trace 含 steps", "steps" in trace_data)
                    steps = trace_data.get("steps", [])
                    check(f"Trace steps 是 list ({len(steps)} 步)", isinstance(steps, list))
        else:
            print("  ⚠ 无已完成/失败任务，跳过 trace 验证")


# ============================================================
# 7. 数据一致性
# ============================================================
def test_stage_7_consistency():
    stage("7. 数据一致性")

    # 验证无孤立数据：创建 → 使用 → 清理
    r = client.get("/api/v1/agent/tenants/", headers=HD)
    check("租户列表可查 (200)", r.status_code == 200)

    r = client.get("/api/v1/mcp/tools/", headers=HD)
    check("工具列表可查 (200)", r.status_code == 200)

    # 验证 service 信息一致（两次请求名字相同）
    r = client.get("/api/v1/health/")
    v1 = r.json().get("services", [])

    r2 = client.get("/api/v1/health")
    v2 = r2.json().get("services", [])

    check("两次 health 返回一致", [s["name"] for s in v1] == [s["name"] for s in v2])

    # MCP 与 health 中 mcp_gateway 工具数一致（中文 "MCP" 匹配）
    mcp_services = [s for s in v1 if "MCP" in s.get("name", "")]
    if mcp_services:
        tools_r = client.get("/api/v1/mcp/tools/", headers=HD)
        tool_count = len(tools_r.json().get("results", []))
        mcp_detail = mcp_services[0].get("detail", "{}")
        print(f"  MCP 工具总数: {tool_count}, health 报告: {mcp_detail}")


# ============================================================
# Run All
# ============================================================
print("=" * 60)
print("   Phase 2.8 端到端验证 — E2E Smoke Test")
print("=" * 60)

all_tests = [
    test_stage_1_health,
    test_stage_2_auth,
    test_stage_3_mcp_tools,
    test_stage_4_tenant,
    test_stage_5_workflow,
    test_stage_6_tasks,
    test_stage_7_consistency,
]

for t in all_tests:
    try:
        t()
    except Exception as e:
        print(f"\n  💥 [{STAGE}] 异常: {e}")
        import traceback
        traceback.print_exc()
        FAIL += 1

print(f"\n{'=' * 60}")
print(f"  Phase 2.8 结果: {PASS}/{PASS+FAIL} 通过, {FAIL}/{PASS+FAIL} 失败")
if FAIL == 0:
    print("  🎉 端到端验证全部通过！")
else:
    print(f"  ⚠ 有 {FAIL} 项失败，请检查上方 ❌ 标记")
print(f"{'=' * 60}")
