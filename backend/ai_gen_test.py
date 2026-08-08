import requests, json

BASE = "http://localhost:8000"
r = requests.post(f"{BASE}/api/auth/login/", json={"username": "admin", "password": "admin123456"})
token = r.json()["access"]
H = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

api_doc = """POST /api/user/register
功能：用户注册
请求参数：
  - username (string, 必填): 用户名，3-20字符
  - password (string, 必填): 密码，6-20字符
  - email (string, 必填): 邮箱地址
返回：
  - code (int): 状态码 200 成功
  - msg (string): 提示信息
  - data.user_id (int): 新用户ID"""

print("调用 AI 生成测试用例...")
print(f"接口文档: {api_doc[:60]}...")
print()

try:
    r = requests.post(f"{BASE}/api/testcases/ai-generate/", json={
        "api_document": api_doc,
        "save_to_db": False
    }, headers=H, timeout=120)
    
    print(f"状态码: {r.status_code}")
    d = r.json()
    
    if r.status_code == 200:
        tcs = d.get("test_cases", [])
        print(f"生成用例数: {len(tcs)}")
        print()
        for i, tc in enumerate(tcs[:5], 1):
            print(f"--- 用例 {i} ---")
            for k, v in tc.items():
                if isinstance(v, str) and len(v) > 80:
                    v = v[:80] + "..."
                print(f"  {k}: {v}")
            print()
        print("[PASS] AI 用例生成成功")
    else:
        print(f"响应: {json.dumps(d, ensure_ascii=False)[:300]}")
        print("[FAIL] AI 用例生成失败")
except Exception as e:
    print(f"[FAIL] 异常: {e}")
