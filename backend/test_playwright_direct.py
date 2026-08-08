"""
直接 Playwright 测试 — 不经过后端 API，验证 Playwright 是否能正常运行
"""
import asyncio
import json
import time
from playwright.async_api import async_playwright

async def test_playwright_direct():
    """打开百度首页 → 搜索 → 验证结果 → 截图"""
    start = time.time()
    results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 720})
        page = await context.new_page()

        # Step 1: 打开百度
        t1 = time.time()
        await page.goto("https://www.baidu.com", timeout=30000)
        results.append({"step": 1, "action": "navigate", "status": "passed", "url": page.url})
        print(f"Step 1: 打开百度 [OK] ({time.time()-t1:.2f}s)")

        # Step 2: 输入搜索词
        t2 = time.time()
        await page.fill("#kw", "Playwright 自动化测试")
        results.append({"step": 2, "action": "fill", "status": "passed"})
        print(f"Step 2: 输入搜索词 [OK] ({time.time()-t2:.2f}s)")

        # Step 3: 点击搜索
        t3 = time.time()
        await page.click("#su")
        await page.wait_for_load_state("networkidle", timeout=15000)
        results.append({"step": 3, "action": "click", "status": "passed"})
        print(f"Step 3: 点击搜索 [OK] ({time.time()-t3:.2f}s)")

        # Step 4: 验证搜索结果有内容
        t4 = time.time()
        content = await page.content()
        assert "Playwright" in content or "自动化测试" in content, "搜索结果中未找到关键词"
        results.append({"step": 4, "action": "assert_text", "status": "passed"})
        print(f"Step 4: 验证搜索结果 [OK] ({time.time()-t4:.2f}s)")

        # Step 5: 截图保存
        t5 = time.time()
        await page.screenshot(path="test_output/screenshot.png", type="png", full_page=True)
        results.append({"step": 5, "action": "screenshot", "status": "passed", "path": "test_output/screenshot.png"})
        print(f"Step 5: 截图保存 [OK] ({time.time()-t5:.2f}s)")

        await browser.close()

    duration = round(time.time() - start, 2)
    result = {
        "status": "passed",
        "duration": duration,
        "steps": len(results),
        "results": results,
    }
    
    # 输出结果
    import os
    os.makedirs("test_output", exist_ok=True)
    with open("test_output/result.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*50}")
    print(f"Sum: PASSED | Time: {duration}s | Steps: {len(results)}")
    print(f"Screenshot: test_output/screenshot.png")
    print(f"Result: test_output/result.json")
    print(f"{'='*50}")
    return result

if __name__ == "__main__":
    asyncio.run(test_playwright_direct())
