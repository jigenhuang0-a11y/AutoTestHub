"""
AI 视觉评估 - 端到端验证

流程：
1. 用 Playwright 打开本地测试页面并截图
2. 将截图 + 测试指令发送给 qwen3-vl-flash
3. 检查模型返回的判断结果

用法：python test_visual_eval.py
"""

import json
import os
import sys
import time

# 确保项目路径在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ============================================================
# 配置区域 - 填入你的 API 信息
# ============================================================
VL_API_KEY = "YOUR_DASHSCOPE_API_KEY"
VL_API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"  # 标准 DashScope 公网地址
VL_MODEL = "qwen3-vl-flash"
# ============================================================


def step_1_generate_test_page():
    """Step 1: 生成本地测试 HTML 页面"""
    print("=" * 60)
    print("Step 1: Generate local test page")
    print("=" * 60)

    output_dir = os.path.join(os.path.dirname(__file__), 'test_output')
    os.makedirs(output_dir, exist_ok=True)

    html_path = os.path.join(output_dir, 'test_page.html')

    html_content = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>Test Page</title>
<style>
body { font-family: Arial; padding: 40px; background: #f5f5f5; }
.login-box { max-width: 400px; margin: 50px auto; padding: 30px;
             background: white; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
h2 { text-align: center; color: #333; }
.form-group { margin-bottom: 15px; }
label { display: block; margin-bottom: 5px; color: #666; }
input { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }
button { width: 100%; padding: 12px; background: #4CAF50; color: white;
         border: none; border-radius: 4px; cursor: pointer; font-size: 16px; }
button:hover { background: #45a049; }
#result { margin-top: 20px; padding: 15px; border-radius: 4px;
          text-align: center; font-weight: bold; }
.success { background: #dff0d8; color: #3c763d; }
.error { background: #f2dede; color: #a94442; }
</style>
</head>
<body>
<div class="login-box">
<h2>User Login</h2>
<form id="loginForm" onsubmit="handleLogin(event)">
<div class="form-group">
<label>Username:</label>
<input type="text" id="username" placeholder="Enter username">
</div>
<div class="form-group">
<label>Password:</label>
<input type="password" id="password" placeholder="Enter password">
</div>
<button type="submit" id="login-btn">Login</button>
</form>
<div id="result"></div>
</div>
<script>
function handleLogin(e) {
e.preventDefault();
var user = document.getElementById('username').value;
var resultDiv = document.getElementById('result');
if (user === 'admin') {
resultDiv.textContent = 'Login successful! Welcome, ' + user;
resultDiv.className = 'success';
} else {
resultDiv.textContent = 'Login failed! Invalid credentials.';
resultDiv.className = 'error';
}
}
</script>
</body>
</html>"""

    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"  Test page created: {html_path}")
    return html_path


def step_2_take_screenshot(html_path):
    """Step 2: Playwright 打开页面、填表、提交、截图"""
    print("\n" + "=" * 60)
    print("Step 2: Take screenshot with Playwright")
    print("=" * 60)

    from playwright.sync_api import sync_playwright

    output_dir = os.path.join(os.path.dirname(__file__), 'test_output')
    screenshot_path = os.path.join(output_dir, 'vl_test_screenshot.png')

    t_start = time.time()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1280, 'height': 720})

        # 打开本地页面
        page.goto(f'file:///{html_path.replace(os.sep, "/")}', timeout=15000)
        print(f"  [OK] Page loaded ({time.time()-t_start:.2f}s)")

        # 填写表单
        page.fill('#username', 'admin')
        page.fill('#password', 'admin123')
        print(f"  [OK] Form filled ({time.time()-t_start:.2f}s)")

        # 点击登录
        page.click('#login-btn')
        page.wait_for_timeout(500)
        print(f"  [OK] Login clicked ({time.time()-t_start:.2f}s)")

        # 截图
        page.screenshot(path=screenshot_path, full_page=False)
        duration = time.time() - t_start
        file_size = os.path.getsize(screenshot_path)
        print(f"  [OK] Screenshot saved: {screenshot_path}")
        print(f"       Size: {file_size/1024:.1f}KB | Time: {duration:.2f}s")

        browser.close()

    return screenshot_path


def step_3_visual_evaluate(screenshot_path):
    """Step 3: 发送截图给 VL 模型做视觉评估"""
    print("\n" + "=" * 60)
    print(f"Step 3: AI Visual Evaluation via {VL_MODEL}")
    print("=" * 60)

    from web_testcases.visual_evaluator import VisualEvaluator

    evaluator = VisualEvaluator(
        api_key=VL_API_KEY,
        api_url=VL_API_URL,
        model=VL_MODEL,
        timeout=30,
    )

    # 定义测试用例
    test_cases = [
        {
            'name': 'Test A: Login success check',
            'instruction': '检查这个网页截图，判断用户是否成功登录了系统',
            'expected': '页面上应该显示 "Welcome, admin" 或类似的登录成功提示',
        },
        {
            'name': 'Test B: Page element verification',
            'instruction': '检查页面是否包含以下元素：登录框、用户名字段、密码字段、登录按钮',
            'expected': '所有表单元素都应该可见且完整',
        },
        {
            'name': 'Test C: Negative case detection',
            'instruction': '检查页面是否显示了错误提示信息（如 Login failed）',
            'expected': '不应显示任何错误信息（因为这是成功的登录截图）',
        },
    ]

    results = []
    
    for i, tc in enumerate(test_cases, 1):
        print(f"\n  --- Test {i}: {tc['name']} ---")
        
        t0 = time.time()
        result = evaluator.evaluate_screenshot(
            screenshot_path=screenshot_path,
            test_instruction=tc['instruction'],
            expected_content=tc['expected'],
        )
        elapsed = time.time() - t0

        verdict_mark = {'pass': '[PASS]', 'fail': '[FAIL]', 'error': '[ERROR]'}
        verdict = result['verdict']
        
        print(f"  Verdict: {verdict_mark.get(verdict, '?')} {verdict.upper()}")
        print(f"  Score:   {result['score']}/100")
        print(f"  Reason:  {result['reason'][:120]}...")
        print(f"  Model:   {result['model_used']}")
        print(f"  Latency: {result['latency_ms']:.0f}ms | Total: {elapsed:.2f}s")

        if result['details']:
            details = result['details']
            if details.get('found_elements'):
                print(f"  Found:   {details['found_elements']}")
            if details.get('missing_elements'):
                print(f"  Missing: {details['missing_elements']}")
            if details.get('issues'):
                print(f"  Issues:  {details['issues']}")

        results.append({
            **tc,
            'result': {
                'verdict': result['verdict'],
                'score': result['score'],
                'reason': result['reason'],
                'latency_ms': result['latency_ms'],
            }
        })

    return results


def main():
    t_total = time.time()

    print("\n" + "#" * 60)
    print("#  AI Visual Evaluation - End-to-End Test")
    print("#  Model: " + VL_MODEL)
    print("#" * 60)

    try:
        # Step 1: 准备测试页面
        html_path = step_1_generate_test_page()

        # Step 2: 截图
        screenshot_path = step_2_take_screenshot(html_path)

        # Step 3: 视觉评估
        eval_results = step_3_visual_evaluate(screenshot_path)

        # ============================================================
        # 结果汇总
        # ============================================================
        total_time = time.time() - t_total
        
        passed = sum(1 for r in eval_results if r['result']['verdict'] == 'pass')
        failed = sum(1 for r in eval_results if r['result']['verdict'] == 'fail')
        errors = sum(1 for r in eval_results if r['result']['verdict'] == 'error')

        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"  Total Tests : {len(eval_results)}")
        print(f"  Passed      : {passed}")
        print(f"  Failed      : {failed}")
        print(f"  Errors      : {errors}")
        print(f"  Total Time  : {total_time:.2f}s")
        print(f"  Model Used  : {VL_MODEL}")
        print("=" * 60)

        # 保存详细结果
        report_path = os.path.join(os.path.dirname(__file__), 'test_output', 'visual_eval_report.json')
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump({
                'model': VL_MODEL,
                'screenshot': screenshot_path,
                'total_time': round(total_time, 2),
                'tests': eval_results,
            }, f, ensure_ascii=False, indent=2)
        print(f"\n  Detailed report saved to: {report_path}")

        if failed == 0 and errors == 0:
            print("\n  >>> ALL TESTS PASSED <<<\n")
            return 0
        else:
            print(f"\n  >>> SOME TESTS FAILED ({failed} fail, {errors} error) <<<\n")
            return 1

    except Exception as e:
        print(f"\n!!! FATAL ERROR: {e}\n")
        import traceback
        traceback.print_exc()
        return 2


if __name__ == '__main__':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.exit(main())
