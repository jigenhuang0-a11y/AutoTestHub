"""
Phase 2.7 后端集成测试（FastAPI TestClient 模式，无需启动服务器）
"""
import os
import sys
import io
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 抑制 OpenTelemetry / httpx 日志噪音
for name in ("opentelemetry", "httpx", "app.core.telemetry"):
    logging.getLogger(name).setLevel(logging.ERROR)

os.environ.setdefault("SERVICE_TOKEN", "test-token")
os.environ.setdefault("PORT", "8005")

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
PASS = 0
FAIL = 0


def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✅ {name}")
    else:
        FAIL += 1
        print(f"  ❌ {name} — {detail}")


# ============================================================
# 1. Health 端点 — services 数组
# ============================================================
def test_health_services():
    r = client.get("/api/v1/health/")
    check("health 返回 200", r.status_code == 200, f"status={r.status_code}")
    data = r.json()
    check("health 有 status 字段", "status" in data)
    check("health 有 services 字段", "services" in data)
    services = data.get("services", [])
    check("services 是 list", isinstance(services, list))
    check(f"services 至少有 2 项 (实际 {len(services)})", len(services) >= 2)
    for svc in services:
        check(f"服务 {svc.get('name','?')[:20]} 有 status", "status" in svc)
    print(f"  → services: {[s['name'][:25] for s in services]}\n")


# ============================================================
# 2. MCP 分类列表
# ============================================================
def test_mcp_categories():
    r = client.get("/api/v1/mcp/tools/categories/", headers={"X-Service-Token": "test-token"})
    check("categories 返回 200", r.status_code == 200, f"status={r.status_code}")
    data = r.json()
    cats = data.get("results", [])
    check("categories 有 results", "results" in data)
    check(f"categories 数量 >= 1 (实际 {len(cats)})", len(cats) >= 1)
    for cat in cats:
        check(f"  {cat.get('name')} 有 label/count/active",
              all(k in cat for k in ["name", "label", "count", "active"]))
    print()


# ============================================================
# 3. MCP 工具列表
# ============================================================
def test_mcp_tools():
    r = client.get("/api/v1/mcp/tools/", headers={"X-Service-Token": "test-token"})
    check("tools 返回 200", r.status_code == 200, f"status={r.status_code}")
    data = r.json()
    check("tools 有 results", "results" in data)
    tools = data.get("results", [])
    check(f"tools 数量 >= 1 (实际 {len(tools)})", len(tools) >= 1)
    if tools:
        check("tool 有 name 字段", "name" in tools[0])
    print()


# ============================================================
# 4. MCP PUT — 工具状态切换
# ============================================================
def test_mcp_put():
    hdrs = {"X-Service-Token": "test-token"}

    # 获取工具列表
    r = client.get("/api/v1/mcp/tools/", headers=hdrs)
    tools = r.json()["results"]
    check("有可用工具进行 PUT 测试", len(tools) > 0, "tools 为空")
    if not tools:
        return

    tool = tools[0]
    tool_name = tool.get("name")
    original_status = tool.get("status", "active")
    print(f"  → 测试工具: {tool_name} (当前: {original_status})")

    # 切换状态
    new_status = "disabled" if original_status == "active" else "active"
    r = client.put(
        f"/api/v1/mcp/tools/{tool_name}/",
        json={"status": new_status},
        headers=hdrs,
    )
    check(f"PUT 返回 200 (实际 {r.status_code})", r.status_code == 200, r.text)
    if r.status_code == 200:
        check(f"状态已切换为 {new_status}", r.json()["status"] == new_status)
        # 恢复
        r = client.put(
            f"/api/v1/mcp/tools/{tool_name}/",
            json={"status": original_status},
            headers=hdrs,
        )
        check(f"状态已恢复为 {original_status}",
              r.status_code == 200 and r.json()["status"] == original_status)

    # 不存在工具 → 404
    r = client.put("/api/v1/mcp/tools/notexists/", json={"status": "active"}, headers=hdrs)
    check("不存在工具返回 404", r.status_code == 404, f"status={r.status_code}")
    print()


# ============================================================
# 5. 认证检查 — 无凭据应拒绝
# ============================================================
def test_auth():
    r = client.get("/api/v1/mcp/tools/")  # 无 header
    check("无凭据访问 MCP 被拒绝 (401/403)",
          r.status_code in (401, 403), f"status={r.status_code}")
    print()


# ============================================================
# Run all
# ============================================================
print("=" * 60)
print("Phase 2.7 后端集成测试 — FastAPI TestClient")
print("=" * 60)
print()

tests = [test_health_services, test_mcp_categories, test_mcp_tools, test_mcp_put, test_auth]
for t in tests:
    try:
        t()
    except Exception as e:
        print(f"  💥 {t.__name__} 异常: {e}")
        import traceback
        traceback.print_exc()
        FAIL += 1

print("=" * 60)
print(f"结果: {PASS}/{PASS+FAIL} 通过, {FAIL}/{PASS+FAIL} 失败")
print("=" * 60)
