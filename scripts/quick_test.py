import requests, json, sys

BASE = "http://8.163.95.60/api"
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzgzOTA2ODA0LCJpYXQiOjE3ODM4MjA0MDQsImp0aSI6ImNmNzU5MDY2ZWE3NDQwNjRiNzU4MzRkNTAyY2ViZGI2IiwidXNlcl9pZCI6IjEifQ.NYWXCP_UYp4AcOGlrnmjIhplPaPj4y7aqu247YHywy4"
HEADERS = {"Content-Type":"application/json", "Authorization": f"Bearer {TOKEN}"}

# 1. API 用例创建
print("[1] API用例创建")
resp = requests.post(f"{BASE}/testcases/", headers=HEADERS, json={
    "name": "订单创建接口冒烟测试",
    "method": "POST",
    "url": "https://api.example.com/orders",
    "headers": {"Content-Type": "application/json"},
    "body": "{\"product_id\":123,\"quantity\":2}",
    "assertions": [{"type": "status_code", "expected": 201}],
    "tags": ["订单", "冒烟测试"],
    "priority": "high",
    "category": "接口测试"
}, timeout=30)
print(f"  Status: {resp.status_code}")
if resp.status_code in (200, 201):
    d = resp.json()
    print(f"  ID: {d.get('id')}")
else:
    print(f"  ERROR: {resp.text[:300]}")

# 2. Web 用例创建
print("\n[2] Web用例创建")
resp = requests.post(f"{BASE}/web-testcases/", headers=HEADERS, json={
    "name": "电商登录流程测试",
    "url": "https://example.com/login",
    "steps": [{"action": "navigate", "target": "https://example.com/login"}],
    "assertions": [{"type": "url_contains", "expected": "/dashboard"}],
    "tags": ["登录", "Web"],
    "priority": "high"
}, timeout=30)
print(f"  Status: {resp.status_code}")
if resp.status_code in (200, 201):
    d = resp.json()
    print(f"  ID: {d.get('id')}")
else:
    print(f"  ERROR: {resp.text[:300]}")

# 3. 数据工厂 - LLM 评测数据
print("\n[3] 数据工厂-LLM评测数据")
resp = requests.post(f"{BASE}/data-factory/generate-llm-dataset/", headers=HEADERS, json={
    "dataset_type": "llm_eval",
    "scenario": "电商平台客服对话场景，用户咨询订单物流状态",
    "record_count": 5,
    "difficulty_distribution": {"easy": 30, "medium": 50, "hard": 20}
}, timeout=120)
print(f"  Status: {resp.status_code}")
if resp.status_code in (200, 201):
    d = resp.json()
    print(f"  Dataset ID: {d.get('dataset_id', d.get('id'))}")
else:
    print(f"  ERROR: {resp.text[:500]}")

# 4. 测试套件创建
print("\n[4] 测试套件创建")
resp = requests.post(f"{BASE}/testsuites/", headers=HEADERS, json={
    "name": "核心链路回归测试套件",
    "description": "包含订单、支付核心流程的回归测试",
    "tags": ["回归", "核心链路"]
}, timeout=30)
print(f"  Status: {resp.status_code}")
if resp.status_code in (200, 201):
    d = resp.json()
    print(f"  ID: {d.get('id')}")
else:
    print(f"  ERROR: {resp.text[:300]}")

# 5. AI 测评师
print("\n[5] AI测评师")
resp = requests.post(f"{BASE}/ai-evaluator/", headers=HEADERS, json={
    "name": "DeepSeek-Chat 客服场景评测",
    "model_name": "deepseek-chat",
    "dataset_id": 1,
    "evaluation_config": {"metrics": ["accuracy", "fluency"], "sampling_rate": 1.0}
}, timeout=30)
print(f"  Status: {resp.status_code}")
if resp.status_code in (200, 201):
    d = resp.json()
    print(f"  ID: {d.get('id')}")
else:
    print(f"  ERROR: {resp.text[:300]}")

# 6. 知识库
print("\n[6] 知识库创建")
resp = requests.post(f"{BASE}/knowledge/knowledge-bases/", headers=HEADERS, json={
    "name": "产品测试规范知识库",
    "description": "API测试规范、Web测试标准、性能测试指标"
}, timeout=30)
print(f"  Status: {resp.status_code}")
if resp.status_code in (200, 201):
    d = resp.json()
    print(f"  ID: {d.get('id')}")
else:
    print(f"  ERROR: {resp.text[:300]}")

# 7. 质量检查
print("\n[7] 质量检查")
resp = requests.post(f"{BASE}/quality-checker/check/", headers=HEADERS, json={
    "check_type": "testcase_quality",
    "target_id": 1,
    "rules": ["assertion_coverage", "naming_convention"]
}, timeout=30)
print(f"  Status: {resp.status_code}")
if resp.status_code in (200, 201, 202):
    print(f"  OK")
else:
    print(f"  ERROR: {resp.text[:300]}")

# 8. 执行历史/数据看板
print("\n[8] 数据看板")
for ep in ["/execution/", "/execution/stats/dashboard/", "/execution/stats/error-trend/?days=7", "/execution/stats/token-trend/?days=7"]:
    resp = requests.get(f"{BASE}{ep}", headers=HEADERS, timeout=30)
    print(f"  {ep}: {resp.status_code}")

# 9. 模型管理
print("\n[9] 模型管理")
resp = requests.get(f"{BASE}/ai-evaluator/models/", headers=HEADERS, timeout=30)
print(f"  /ai-evaluator/models/: {resp.status_code}")

# 10. 技能库
print("\n[10] 技能库")
resp = requests.get(f"{BASE}/agent/skills/", headers=HEADERS, timeout=30)
print(f"  /agent/skills/: {resp.status_code}")
resp = requests.get(f"{BASE}/mcp/tools/", headers=HEADERS, timeout=30)
print(f"  /mcp/tools/: {resp.status_code}")

print("\n=== 测试完成 ===")
