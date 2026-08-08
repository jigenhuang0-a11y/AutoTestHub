"""纯本地 Playwright 测试 — 不需要网络，使用本地 HTML"""
import asyncio, json, time, os
from playwright.async_api import async_playwright

LOCAL_HTML = """
<html>
<head><title>测试页面</title></head>
<body>
    <h1>欢迎来到测试平台</h1>
    <input type="text" id="username" placeholder="请输入用户名" />
    <button id="login-btn">登录</button>
    <div id="result"></div>
    <script>
        document.getElementById('login-btn').addEventListener('click', function() {
            var name = document.getElementById('username').value;
            document.getElementById('result').innerText = '欢迎, ' + name + '!';
        });
    </script>
</body>
</html>
"""

async def main():
    os.makedirs("test_output", exist_ok=True)

    # 保存本地 HTML
    html_path = "test_output/test_page.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(LOCAL_HTML)
    file_url = "file:///" + os.path.abspath(html_path).replace("\\", "/")

    start = time.time()
    step_results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Step 1: 打开本地页面
        t1 = time.time()
        await page.goto(file_url)
        title = await page.title()
        step_results.append({"step": 1, "action": "navigate", "status": "passed", "title": title})
        print(f"[OK] Step 1: Navigate to local page | {time.time()-t1:.2f}s | Title: {title}")

        # Step 2: 填写输入框
        t2 = time.time()
        await page.fill("#username", "admin")
        val = await page.input_value("#username")
        step_results.append({"step": 2, "action": "fill", "status": "passed", "value": val})
        print(f"[OK] Step 2: Fill input | {time.time()-t2:.2f}s | Value: {val}")

        # Step 3: 点击登录按钮
        t3 = time.time()
        await page.click("#login-btn")
        await page.wait_for_timeout(500)
        step_results.append({"step": 3, "action": "click", "status": "passed"})
        print(f"[OK] Step 3: Click button | {time.time()-t3:.2f}s")

        # Step 4: 验证结果
        t4 = time.time()
        result_text = await page.text_content("#result")
        assert "admin" in result_text, f"Expected 'admin' in result, got: {result_text}"
        step_results.append({"step": 4, "action": "assert_text", "status": "passed", "found": result_text})
        print(f"[OK] Step 4: Assert text | {time.time()-t4:.2f}s | Found: {result_text}")

        # Step 5: 截图
        t5 = time.time()
        await page.screenshot(path="test_output/final_screenshot.png", full_page=True)
        step_results.append({"step": 5, "action": "screenshot", "status": "passed"})
        print(f"[OK] Step 5: Screenshot | {time.time()-t5:.2f}s")

        await browser.close()

    duration = round(time.time() - start, 2)
    result = {
        "status": "passed",
        "duration": duration,
        "total_steps": len(step_results),
        "step_results": step_results,
    }
    with open("test_output/result.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*50}")
    print(f"ALL PASSED | Time: {duration}s | Steps: {len(step_results)}/5")
    print(f"{'='*50}")
    return result

if __name__ == "__main__":
    asyncio.run(main())
