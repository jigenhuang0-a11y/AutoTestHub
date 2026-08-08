"""
测试完整 Playwright 引擎管线：
1. 模拟用户创建用例（步骤模式）
2. 调用 run_web_test() 
3. 验证脚本生成 → 子进程执行 → 结果解析 全链路
"""
import sys, os, json, time
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ai_test_platform.settings")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Django 初始化
import django
django.setup()

from web_testcases.playwright_engine import run_web_test, _generate_playwright_script

# 模拟一个步骤模式的测试用例
class MockCase:
    pass

case = MockCase()
case.engine = "playwright"
case.title = "本地登录测试"
case.target_url = "file:///" + os.path.abspath("test_output/test_page.html").replace("\\", "/")
case.browser_type = "chromium"
case.headless = True
case.viewport = {"width": 1280, "height": 720}
case.steps = [
    {"action": "navigate", "params": {"url": case.target_url}, "description": "打开测试页面"},
    {"action": "fill", "params": {"selector": "#username", "value": "admin"}, "description": "输入用户名"},
    {"action": "click", "params": {"selector": "#login-btn"}, "description": "点击登录按钮"},
    {"action": "wait_for", "params": {"type": "time", "time": 500}, "description": "等待响应"},
]
case.ai_prompt = ""
case.assertions = [
    {"type": "text_exists", "expected": "admin", "selector": "#result"},
]
case.screenshot_enabled = True
case.full_page_screenshot = True
case.record_video = False

print("=" * 60)
print("FULL ENGINE PIPELINE TEST")
print("=" * 60)
print(f"Engine: {case.engine}")
print(f"Target: {case.target_url}")
print(f"Steps: {len(case.steps)}")
print(f"Assertions: {len(case.assertions)}")
print(f"Browser: {case.browser_type} (headless={case.headless})")
print("-" * 60)

start = time.time()
result = run_web_test(case)
duration = round(time.time() - start, 2)

print(f"\n===== EXECUTION RESULT =====")
print(f"Status: {result['status'].upper()}")
print(f"Duration: {result['duration']}s (pipeline overhead: {result['duration'] - result.get('duration',0):.2f}s)")
print(f"Steps completed: {len(result.get('steps_results', []))}")
print(f"Assertion errors: {len(result.get('assertion_errors', []))}")

if result.get('assertion_errors'):
    for e in result['assertion_errors']:
        print(f"  - {e}")

if result.get('error'):
    print(f"Script Error: {result['error'][:200]}")

if result.get('screenshot_path'):
    size = os.path.getsize(result['screenshot_path']) if os.path.exists(result['screenshot_path']) else 0
    print(f"Screenshot: {result['screenshot_path']} ({size} bytes)")

if result.get('steps_results'):
    print("\n----- Step Details -----")
    for s in result['steps_results']:
        print(f"  Step {s['step']}: {s['action']} -> {s['status']}")

print(f"\n===== {'PASSED' if result['status'] == 'passed' else 'FAILED'} =====")
print(f"Total pipeline time: {duration}s")
print("=" * 60)
