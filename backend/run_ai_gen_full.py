import subprocess
import sys
import time
import requests
import json

BASE = "http://localhost:8000"

# 启动 Django
print("[1/4] 启动 Django 子进程...")
proc = subprocess.Popen(
    [sys.executable, "manage.py", "runserver", "0.0.0.0:8000"],
    cwd=r"d:\AI_Project\ai-test-platform\backend",
    stdout=open("django_auto.log", "w", encoding="utf-8"),
    stderr=subprocess.STDOUT,
)

# 等待就绪
time.sleep(12)
for _ in range(20):
    try:
        r = requests.get(f"{BASE}/api/auth/login/", timeout=3)
        if r.status_code in (200, 405):
            break
    except Exception:
        pass
    time.sleep(1)
else:
    print("Django 启动失败")
    proc.terminate()
    sys.exit(1)

print("[2/4] Django 就绪，开始登录...")
r = requests.post(f"{BASE}/api/auth/login/", json={"username": "admin", "password": "admin123456"}, timeout=10)
if r.status_code != 200:
    print(f"登录失败: {r.status_code} {r.text[:200]}")
    proc.terminate()
    sys.exit(1)
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

print("[3/4] 调用 AI 生成测试用例...")
r = requests.post(f"{BASE}/api/testcases/ai-generate/", json={"api_document": api_doc, "save_to_db": False}, headers=H, timeout=120)
print(f"状态码: {r.status_code}")
d = r.json()
print(f"响应: {json.dumps(d, ensure_ascii=False)[:500]}")

if r.status_code == 200:
    tcs = d.get("test_cases", [])
    print(f"\n生成用例数: {len(tcs)}")
    for i, tc in enumerate(tcs[:3], 1):
        print(f"\n--- 用例 {i} ---")
        for k, v in tc.items():
            if isinstance(v, str) and len(v) > 80:
                v = v[:80] + "..."
            print(f"  {k}: {v}")
else:
    print(f"\n[FAIL] AI 生成失败")

print("\n[4/4] 关闭 Django 子进程...")
proc.terminate()
proc.wait(timeout=5)
print("完成")
