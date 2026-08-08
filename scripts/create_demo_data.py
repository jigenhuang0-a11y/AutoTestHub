import requests, json

BASE = "http://8.163.95.60/api"
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzgzOTA2ODA0LCJpYXQiOjE3ODM4MjA0MDQsImp0aSI6ImNmNzU5MDY2ZWE3NDQwNjRiNzU4MzRkNTAyY2ViZGI2IiwidXNlcl9pZCI6IjEifQ.NYWXCP_UYp4AcOGlrnmjIhplPaPj4y7aqu247YHywy4"
HEADERS = {"Content-Type":"application/json", "Authorization": f"Bearer {TOKEN}"}

print("=== 批量创建真实演示数据 ===")

# 1. 创建更多 API 用例
api_cases = [
    {"title": "用户登录接口测试", "description": "验证用户名密码登录", "api_endpoint": "https://api.example.com/auth/login", "method": "POST", "request_body": {"username": "test", "password": "123456"}, "assertion_rules": [{"type": "status_code", "expected": 200}, {"type": "json_path", "path": "$.token", "operator": "exists"}], "priority": "P0", "tags": ["登录", "认证"]},
    {"title": "商品详情查询测试", "description": "验证根据商品ID查询详情", "api_endpoint": "https://api.example.com/products/123", "method": "GET", "assertion_rules": [{"type": "status_code", "expected": 200}, {"type": "json_path", "path": "$.product.name", "operator": "exists"}], "priority": "P1", "tags": ["商品", "查询"]},
    {"title": "购物车添加测试", "description": "添加商品到购物车", "api_endpoint": "https://api.example.com/cart/add", "method": "POST", "request_body": {"product_id": 456, "quantity": 1}, "assertion_rules": [{"type": "status_code", "expected": 200}, {"type": "json_path", "path": "$.cart_count", "expected": 1}], "priority": "P1", "tags": ["购物车", "订单"]},
    {"title": "支付接口测试", "description": "模拟支付流程", "api_endpoint": "https://api.example.com/payment", "method": "POST", "request_body": {"order_id": "ORD-2026-001", "amount": 199.99, "payment_method": "alipay"}, "assertion_rules": [{"type": "status_code", "expected": 200}, {"type": "json_path", "path": "$.payment_status", "expected": "success"}], "priority": "P0", "tags": ["支付", "核心链路"]},
]
for i, case in enumerate(api_cases):
    resp = requests.post(f"{BASE}/testcases/", headers=HEADERS, json=case, timeout=30)
    print(f"  API用例 {i+1}: {resp.status_code} - {case['title']}")

# 2. 创建更多 Web 用例
web_cases = [
    {"title": "商品搜索流程测试", "description": "首页搜索商品并查看详情", "engine": "playwright", "target_url": "https://example.com", "browser_type": "chromium", "steps": [{"action": "navigate", "params": {"url": "https://example.com"}}, {"action": "fill", "params": {"selector": "#search", "value": "iPhone 16"}}, {"action": "click", "params": {"selector": "#search-btn"}}, {"action": "wait_for", "params": {"selector": ".product-list", "timeout": 5000}}], "assertions": [{"type": "element_visible", "selector": ".product-list"}], "priority": "P1", "tags": ["搜索", "Web"]},
    {"title": "订单提交流程测试", "description": "从购物车到订单提交", "engine": "playwright", "target_url": "https://example.com/cart", "browser_type": "chromium", "steps": [{"action": "navigate", "params": {"url": "https://example.com/cart"}}, {"action": "click", "params": {"selector": "#checkout-btn"}}, {"action": "fill", "params": {"selector": "#address", "value": "北京市朝阳区"}}, {"action": "click", "params": {"selector": "#submit-order"}}], "assertions": [{"type": "url_contains", "expected": "/order-success"}], "priority": "P0", "tags": ["订单", "Web", "核心链路"]},
]
for i, case in enumerate(web_cases):
    resp = requests.post(f"{BASE}/web-testcases/", headers=HEADERS, json=case, timeout=30)
    print(f"  Web用例 {i+1}: {resp.status_code} - {case['title']}")

# 3. 创建知识库文档
print("\n[3] 上传知识库文档")
kb_id = 6  # 已创建的知识库
# 先查看知识库文档列表
resp = requests.get(f"{BASE}/knowledge/documents/?knowledge_base={kb_id}", headers=HEADERS, timeout=30)
print(f"  知识库文档列表: {resp.status_code}")

# 4. 创建更多数据集
print("\n[4] 创建更多数据集")
resp = requests.post(f"{BASE}/data-factory/datasets/", headers=HEADERS, json={
    "name": "接口测试数据集-订单场景",
    "dataset_type": "structured",
    "business_domain": "order",
    "description": "订单创建、支付、查询等接口测试数据",
    "record_count": 50,
    "status": "completed"
}, timeout=30)
print(f"  结构化数据集: {resp.status_code}")

resp = requests.post(f"{BASE}/data-factory/datasets/", headers=HEADERS, json={
    "name": "Web测试数据集-用户登录",
    "dataset_type": "structured",
    "business_domain": "user",
    "description": "用户登录场景测试数据，包含各种用户名密码组合",
    "record_count": 30,
    "status": "completed"
}, timeout=30)
print(f"  结构化数据集2: {resp.status_code}")

# 5. 创建 AI 测评任务
print("\n[5] 创建更多AI测评任务")
resp = requests.post(f"{BASE}/ai-evaluator/tasks/", headers=HEADERS, json={
    "name": "GPT-4o 客服场景评测",
    "model": "gpt-4o",
    "dataset": 1,
    "metrics": ["accuracy", "fluency", "safety"]
}, timeout=30)
print(f"  测评任务2: {resp.status_code}")

resp = requests.post(f"{BASE}/ai-evaluator/tasks/", headers=HEADERS, json={
    "name": "Qwen-Max 代码生成评测",
    "model": "qwen-max",
    "dataset": 1,
    "metrics": ["accuracy", "code_quality"]
}, timeout=30)
print(f"  测评任务3: {resp.status_code}")

# 6. 知识库问答 (修正端点)
print("\n[6] 知识库问答")
resp = requests.post(f"{BASE}/knowledge/knowledge-bases/6/ask_stream/", headers=HEADERS, json={
    "question": "API测试用例应该如何设计断言？"
}, timeout=60)
print(f"  知识库问答: {resp.status_code}")
if resp.status_code == 200:
    print(f"  响应内容: {resp.text[:200]}")

# 7. 创建质量检查任务
print("\n[7] 创建质量检查任务")
resp = requests.post(f"{BASE}/quality-checker/tasks/", headers=HEADERS, json={
    "name": "登录接口用例质量检查",
    "check_type": "testcase",
    "target": 1,
    "rules": ["assertion_coverage", "naming_convention", "parameter_completeness"]
}, timeout=30)
print(f"  质量检查任务: {resp.status_code}")

resp = requests.post(f"{BASE}/quality-checker/tasks/", headers=HEADERS, json={
    "name": "Web登录流程质量检查",
    "check_type": "web_testcase",
    "target": 1,
    "rules": ["step_coverage", "assertion_completeness"]
}, timeout=30)
print(f"  质量检查任务2: {resp.status_code}")

# 8. 查询最终数据量
print("\n=== 最终数据量统计 ===")
for ep, name in [
    ("/testcases/?page=1&page_size=1", "API用例"),
    ("/web-testcases/?page=1&page_size=1", "Web用例"),
    ("/testsuites/?page=1&page_size=1", "测试套件"),
    ("/data-factory/datasets/?page=1&page_size=1", "数据集"),
    ("/ai-evaluator/tasks/?page=1&page_size=1", "AI测评任务"),
    ("/knowledge/knowledge-bases/?page=1&page_size=1", "知识库"),
    ("/quality-checker/tasks/?page=1&page_size=1", "质量检查"),
    ("/execution/?page=1&page_size=1", "执行历史"),
]:
    resp = requests.get(f"{BASE}{ep}", headers=HEADERS, timeout=30)
    if resp.status_code == 200:
        d = resp.json()
        if isinstance(d, list):
            count = len(d)
        elif isinstance(d, dict):
            count = d.get("count", len(d.get("results", [])))
        else:
            count = 0
        print(f"  {name}: {count}")
    else:
        print(f"  {name}: fail({resp.status_code})")

print("\n=== 演示数据创建完成 ===")
