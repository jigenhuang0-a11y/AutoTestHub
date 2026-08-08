import requests, json

BASE = "http://localhost:8000"
r = requests.post(f"{BASE}/api/auth/login/", json={"username": "admin", "password": "admin123456"})
token = r.json()["access"]
H = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

p = f = 0
tests = [
    ("用例列表", "GET", "/api/testcases/"),
    ("执行列表", "GET", "/api/execution/"),
    ("执行统计", "GET", "/api/execution/stats/"),
    ("RAG文档", "GET", "/api/knowledge/documents/"),
    ("RAG知识库", "GET", "/api/knowledge/knowledge-bases/"),
    ("RAG搜索", "GET", "/api/knowledge/documents/?search=API"),
    ("AI测评", "GET", "/api/ai-evaluator/tasks/"),
    ("测评健康", "GET", "/api/ai-evaluator/tasks/health/"),
    ("性能用例", "GET", "/api/performance/"),
    ("性能执行", "GET", "/api/performance/executions/"),
    ("Agent状态", "GET", "/api/agent/status/"),
    ("MCP工具", "GET", "/api/mcp/tools/"),
]

for name, method, url in tests:
    try:
        resp = requests.request(method, BASE + url, headers=H, timeout=5)
        if resp.status_code == 200:
            cnt = resp.json().get("count", len(resp.json()) if isinstance(resp.json(), list) else "?")
            print(f"  [OK] {name}: 200 ({cnt} items)")
            p += 1
        else:
            print(f"  [XX] {name}: {resp.status_code}")
            f += 1
    except Exception as e:
        print(f"  [XX] {name}: {str(e)[:60]}")
        f += 1

print(f"\n  TOTAL: {p}/{p+f} PASSED")
