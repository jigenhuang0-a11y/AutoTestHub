"""Auto-generated Playwright test script"""
import asyncio
import json
import re
from playwright.async_api import async_playwright

OUTPUT_DIR = r"C:/Temp/test_output"
RESULT_FILE = r"C:/Temp/test_output/result.json"
SCREENSHOTS_DIR = r"C:/Temp/test_output/screenshots"
STEPS_DATA = json.loads(json.dumps([{"action": "navigate", "params": {"url": "file:///D:/AI_Project/ai-test-platform/backend/test_output/test_page.html"}, "description": "打开测试页面"}, {"action": "fill", "params": {"selector": "#username", "value": "admin"}, "description": "输入用户名"}, {"action": "click", "params": {"selector": "#login-btn"}, "description": "点击登录"}, {"action": "wait_for", "params": {"type": "time", "time": 500}, "description": "等待响应"}], ensure_ascii=False))[1:-1]
ASSERTIONS_DATA = json.loads(json.dumps([{"type": "text_exists", "expected": "admin", "selector": "#result"}], ensure_ascii=False))[1:-1]

async def main():
    step_results = []
    assertion_errors = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=true)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 720},
            record_video_dir=r"C:/Temp/test_output/videos" if false else None
        )
        page = await context.new_page()

        # 设置默认超时
        page.set_default_timeout(30000)
        page.set_default_navigation_timeout(60000)

        try:
            # ========== 执行步骤 ==========
            # Step 1: 打开测试页面
            await page.goto('file:///D:/AI_Project/ai-test-platform/backend/test_output/test_page.html')
            step_results.append({'step': 1, 'action': 'navigate', 'status': 'completed'})


            # Step 2: 输入用户名
            await page.fill("#username", "admin")
            step_results.append({'step': 2, 'action': 'fill', 'status': 'completed'})


            # Step 3: 点击登录
            await page.click("#login-btn")
            step_results.append({'step': 3, 'action': 'click', 'status': 'completed'})


            # Step 4: 等待响应
            await page.wait_for_timeout(500)
            step_results.append({'step': 4, 'action': 'wait_for', 'status': 'completed'})



            # ========== 执行断言 ==========
            # Assertion 1
            text_content = (await page.text_content("#result") or '')
            assert "admin" in text_content, f'文本断言失败: 未找到 admin'

            
            final_status = "passed"

        except AssertionError as e:
            final_status = "failed"
            assertion_errors.append(str(e))
        except Exception as e:
            final_status = "error"
            error_msg = str(e)
        
        # 最终截图
        if true:
            try:
                await page.screenshot(
                    path=f"{SCREENSHOTS_DIR}/final.png",
                    type="png",
                    full_page=true
                )
            except Exception:
                pass

        await browser.close()

    # 写入结果
    result = {
        "status": final_status,
        "steps_results": step_results,
        "assertion_errors": assertion_errors,
        "screenshot_path": f"{SCREENSHOTS_DIR}/final.png" if true else None,
        "video_path": None,
        "error": locals().get("error_msg", None),
    }

    with open(RESULT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    asyncio.run(main())
