"""自动截图脚本 - 可靠登录+等待页面加载"""
import os, sys, time, requests
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCREENSHOT_DIR = PROJECT_ROOT / "docs" / "screenshots"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

BASE_URL = "http://8.163.86.47:8000"
USERNAME = "admin"
PASSWORD = "admin123"

PAGES = [
    ("dashboard", "/dashboard"),
    ("testcases", "/testcases"),
    ("ai_generate", "/ai-generate"),
    ("execution", "/execution"),
    ("knowledge", "/knowledge"),
    ("ai_eval", "/ai-evaluator"),
    ("web_auto", "/web-testcases"),
    ("performance", "/perf-testcases"),
    ("models", "/model-manage"),
    ("data_factory", "/data-factory"),
]


def main():
    from playwright.sync_api import sync_playwright

    print(f"[*] Target: {BASE_URL}")
    print(f"[*] Output: {SCREENSHOT_DIR}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            ignore_https_errors=True,
        )
        page = context.new_page()

        # 访问登录页
        print("[*] Loading login page...")
        page.goto(f"{BASE_URL}/login", timeout=30000)
        time.sleep(2)

        # 点击测试账号卡片（更可靠）
        print(f"[*] Clicking test account card...")
        try:
            card = page.locator(".account-card").first
            card.wait_for(timeout=10000)
            card.click()
            time.sleep(1)
        except Exception as e:
            print(f"[!] Card click failed: {e}, fallback to manual fill")
            page.locator("input[placeholder*='用户名']").fill(USERNAME)
            page.locator("input[placeholder*='密码']").fill(PASSWORD)

        # 点击登录按钮
        print(f"[*] Clicking login button...")
        login_btn = page.locator(".login-btn").first
        login_btn.wait_for(timeout=10000)
        login_btn.click()

        # 等待登录完成：URL 从 /login 变为 /
        print(f"[*] Waiting for login redirect...")
        try:
            page.wait_for_url(lambda url: "/login" not in url, timeout=15000)
            print(f"[*] Redirected to: {page.url}")
        except Exception as e:
            print(f"[!] Redirect timeout: {e}")

        time.sleep(3)

        # 检查是否已登录
        token = page.evaluate("() => localStorage.getItem('access_token')")
        if token:
            print(f"[*] Login confirmed, token length: {len(token)}")
        else:
            print(f"[!] No token found, login may have failed")

        # 保存登录页截图
        page.screenshot(path=str(SCREENSHOT_DIR / "login.png"), full_page=False)
        print(f"[*] Saved login.png")

        # 逐个截图
        success = 0
        for name, path in PAGES:
            try:
                print(f"  -> {name}: {path}")
                page.goto(f"{BASE_URL}{path}", timeout=30000, wait_until="networkidle")
                time.sleep(3)
                page.screenshot(path=str(SCREENSHOT_DIR / f"{name}.png"), full_page=False)
                success += 1
                print(f"     OK: {name}.png")
            except Exception as e:
                print(f"     FAIL: {e}")
                try:
                    page.screenshot(path=str(SCREENSHOT_DIR / f"{name}.png"))
                except:
                    pass

        browser.close()
        print(f"\n[Done] {success}/{len(PAGES)} screenshots saved")


if __name__ == "__main__":
    main()
