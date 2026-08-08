import requests, json, sys

BASE = "http://8.163.95.60/api"
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzgzOTA2ODA0LCJpYXQiOjE3ODM4MjA0MDQsImp0aSI6ImNmNzU5MDY2ZWE3NDQwNjRiNzU4MzRkNTAyY2ViZGI2IiwidXNlcl9pZCI6IjEifQ.NYWXCP_UYp4AcOGlrnmjIhplPaPj4y7aqu247YHywy4"
HEADERS = {"Content-Type":"application/json", "Authorization": f"Bearer {TOKEN}"}

results = {"passed": 0, "failed": 0, "errors": [], "data": {}}

def log(name, status, detail="", error=None):
    icon = "OK" if status else "FAIL"
    print(f"  [{icon}] {name}")
    if error:
        print(f"      ERROR: {error}")
    if detail:
        print(f"      DETAIL: {detail}")
    if status:
        results["passed"] += 1
    else:
        results["failed"] += 1
        if error:
            results["errors"].append(f"{name}: {error}")

# 1. API 用例创建 (修正字段名)
print("[1] API用例创建")
resp = requests.post(f"{BASE}/testcases/", headers=HEADERS, json={
    "title": "订单创建接口冒烟测试",
    "description": "验证订单创建接口的基本功能",
    "api_endpoint": "https://api.example.com/orders",
    "method": "POST",
    "headers": {"Content-Type": "application/json"},
    "request_body": {"product_id": 123, "quantity": 2},
    "assertion_rules": [
        {"type": "status_code", "expected": 201},
        {"type": "json_path", "path": "$.order_id", "operator": "exists"}
    ],
    "priority": "P1",
    "status": "active",
    "tags": ["订单", "冒烟测试"]
}, timeout=30)
if resp.status_code in (200, 201):
    d = resp.json()
    tc_id = d.get("id")
    log("API用例创建", True, f"ID={tc_id}")
    results["data"]["api_tc_id"] = tc_id
else:
    log("API用例创建", False, error=f"HTTP {resp.status_code}: {resp.text[:300]}")

# 2. Web 用例创建 (修正字段名和step格式)
print("[2] Web用例创建")
resp = requests.post(f"{BASE}/web-testcases/", headers=HEADERS, json={
    "title": "电商登录流程测试",
    "description": "验证用户登录到仪表盘的核心流程",
    "engine": "playwright",
    "target_url": "https://example.com/login",
    "browser_type": "chromium",
    "headless": True,
    "steps": [
        {"action": "navigate", "params": {"url": "https://example.com/login"}},
        {"action": "fill", "params": {"selector": "#username", "value": "test_user"}},
        {"action": "fill", "params": {"selector": "#password", "value": "test_pass"}},
        {"action": "click", "params": {"selector": "#login-btn"}},
        {"action": "wait_for", "params": {"selector": ".dashboard", "timeout": 5000}}
    ],
    "assertions": [
        {"type": "url_contains", "expected": "/dashboard"},
        {"type": "element_visible", "selector": ".user-profile"}
    ],
    "priority": "P1",
    "status": "active",
    "tags": ["登录", "Web", "冒烟测试"]
}, timeout=30)
if resp.status_code in (200, 201):
    d = resp.json()
    wc_id = d.get("id")
    log("Web用例创建", True, f"ID={wc_id}")
    results["data"]["web_tc_id"] = wc_id
else:
    log("Web用例创建", False, error=f"HTTP {resp.status_code}: {resp.text[:400]}")

# 3. 数据工厂-LLM评测数据 (修正端点)
print("[3] 数据工厂-LLM评测数据")
resp = requests.post(f"{BASE}/data-factory/datasets/generate_llm_dataset/", headers=HEADERS, json={
    "scenario": "电商平台客服对话场景，用户咨询订单物流状态",
    "positive_count": 2,
    "negative_count": 1,
    "boundary_count": 1,
    "languages": ["zh"]
}, timeout=120)
if resp.status_code in (200, 201):
    d = resp.json()
    ds_id = d.get("dataset_id", d.get("id"))
    log("数据工厂-LLM评测", True, f"Dataset ID={ds_id}")
    results["data"]["llm_ds_id"] = ds_id
else:
    log("数据工厂-LLM评测", False, error=f"HTTP {resp.status_code}: {resp.text[:400]}")

# 4. 测试套件创建
print("[4] 测试套件创建")
resp = requests.post(f"{BASE}/testsuites/", headers=HEADERS, json={
    "name": "核心链路回归测试套件",
    "description": "包含订单、支付核心流程的回归测试",
    "tags": ["回归", "核心链路"]
}, timeout=30)
if resp.status_code in (200, 201):
    d = resp.json()
    suite_id = d.get("id")
    log("测试套件创建", True, f"ID={suite_id}")
    results["data"]["suite_id"] = suite_id
else:
    log("测试套件创建", False, error=f"HTTP {resp.status_code}: {resp.text[:300]}")

# 5. AI测评师 (修正端点)
print("[5] AI测评师")
resp = requests.post(f"{BASE}/ai-evaluator/tasks/", headers=HEADERS, json={
    "name": "DeepSeek-Chat 客服场景评测",
    "model": "deepseek-chat",
    "dataset": results["data"].get("llm_ds_id", 1),
    "metrics": ["accuracy", "fluency"]
}, timeout=30)
if resp.status_code in (200, 201):
    d = resp.json()
    eval_id = d.get("id")
    log("AI测评师-创建任务", True, f"ID={eval_id}")
    results["data"]["eval_id"] = eval_id
else:
    log("AI测评师-创建任务", False, error=f"HTTP {resp.status_code}: {resp.text[:400]}")

# 6. 知识库创建
print("[6] 知识库创建")
resp = requests.post(f"{BASE}/knowledge/knowledge-bases/", headers=HEADERS, json={
    "name": "产品测试规范知识库",
    "description": "API测试规范、Web测试标准、性能测试指标"
}, timeout=30)
if resp.status_code in (200, 201):
    d = resp.json()
    kb_id = d.get("id")
    log("知识库创建", True, f"ID={kb_id}")
    results["data"]["kb_id"] = kb_id
else:
    log("知识库创建", False, error=f"HTTP {resp.status_code}: {resp.text[:300]}")

# 7. 质量检查 (修正端点)
print("[7] 质量检查")
resp = requests.post(f"{BASE}/quality-checker/tasks/", headers=HEADERS, json={
    "name": "API用例质量检查",
    "check_type": "testcase",
    "target": results["data"].get("api_tc_id", 1),
    "rules": ["assertion_coverage", "naming_convention"]
}, timeout=30)
if resp.status_code in (200, 201, 202):
    log("质量检查", True)
else:
    log("质量检查", False, error=f"HTTP {resp.status_code}: {resp.text[:400]}")

# 8. 数据看板
print("[8] 数据看板")
for ep in ["/execution/", "/execution/stats/dashboard/", "/execution/stats/error-trend/?days=7", "/execution/stats/token-trend/?days=7"]:
    resp = requests.get(f"{BASE}{ep}", headers=HEADERS, timeout=30)
    log(f"数据看板 {ep}", resp.status_code == 200)

# 9. 模型管理
print("[9] 模型管理")
resp = requests.get(f"{BASE}/ai-evaluator/models/", headers=HEADERS, timeout=30)
log("模型列表", resp.status_code == 200)

# 10. 技能库 (修正端点)
print("[10] 技能库")
resp = requests.get(f"{BASE}/agent/tasks/", headers=HEADERS, timeout=30)
log("Agent任务列表", resp.status_code == 200)

# 11. MCP工具
print("[11] MCP工具")
resp = requests.get(f"{BASE}/mcp/tools/", headers=HEADERS, timeout=30)
log("MCP工具列表", resp.status_code == 200, detail=f"Status: {resp.status_code}")

# 12. 知识库问答
print("[12] 知识库问答")
resp = requests.post(f"{BASE}/knowledge/ask/", headers=HEADERS, json={
    "question": "API测试用例应该如何设计断言？"
}, timeout=60)
log("知识库问答", resp.status_code == 200, detail=f"Status: {resp.status_code}")

# 13. 用例列表查询
print("[13] 用例列表查询")
resp = requests.get(f"{BASE}/testcases/?page=1&page_size=10", headers=HEADERS, timeout=30)
log("API用例列表", resp.status_code == 200)

# 14. Web用例列表
resp = requests.get(f"{BASE}/web-testcases/?page=1&page_size=10", headers=HEADERS, timeout=30)
log("Web用例列表", resp.status_code == 200)

# 15. 数据集列表
resp = requests.get(f"{BASE}/data-factory/datasets/?page=1&page_size=10", headers=HEADERS, timeout=30)
log("数据集列表", resp.status_code == 200)

# 报告
print("\n" + "=" * 50)
print("测试报告")
print("=" * 50)
total = results["passed"] + results["failed"]
print(f"  通过: {results['passed']}")
print(f"  失败: {results['failed']}")
print(f"  总计: {total}")
if total > 0:
    print(f"  成功率: {results['passed']/total*100:.1f}%")
print(f"\n  创建的数据:")
for k, v in results["data"].items():
    print(f"    {k}: {v}")
if results["errors"]:
    print(f"\n  错误列表:")
    for e in results["errors"]:
        print(f"    - {e}")
print("=" * 50)

# 保存报告
with open("d:/AI_Project/ai-test-platform/scripts/test_report_v2.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print("  报告已保存: test_report_v2.json")
