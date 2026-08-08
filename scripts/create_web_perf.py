# -*- coding: utf-8 -*-
import requests, json, time

BASE = "http://8.163.95.60"
LOGIN = f"{BASE}/api/auth/login/"
WEBCASES = f"{BASE}/api/web-testcases/"
PERF = f"{BASE}/api/performance/"

def get_token():
    r = requests.post(LOGIN, json={"username":"admin","password":"admin123"}, timeout=30)
    return r.json().get("access", "")

def safe_json(resp):
    try:
        return resp.json()
    except Exception:
        return None

def main():
    token = get_token()
    if not token:
        print("LOGIN FAILED")
        return
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    print("Token OK")

    # ========== 创建 Web 测试用例 ==========
    web_cases = [
        {
            "title": "登录页流程验证",
            "description": "验证用户登录页面的完整流程，包括表单输入、提交和登录成功后的跳转",
            "engine": "playwright",
            "target_url": "https://example.com/login",
            "browser_type": "chromium",
            "headless": True,
            "viewport": {"width": 1280, "height": 720},
            "steps": [
                {"action": "navigate", "params": {"url": "https://example.com/login"}},
                {"action": "fill", "params": {"selector": "#username", "value": "testuser"}},
                {"action": "fill", "params": {"selector": "#password", "value": "Test123456"}},
                {"action": "click", "params": {"selector": "#login-btn"}},
                {"action": "wait_for", "params": {"selector": ".dashboard", "timeout": 5000}}
            ],
            "assertions": [
                {"type": "url_contains", "expected": "dashboard"},
                {"type": "text_exists", "expected": "欢迎回来"}
            ],
            "priority": "P0",
            "status": "active",
            "tags": ["登录", "冒烟测试"],
            "screenshot_enabled": True,
            "full_page_screenshot": False,
            "record_video": False
        },
        {
            "title": "商品搜索与筛选",
            "description": "验证商品列表页面的搜索和筛选功能",
            "engine": "playwright",
            "target_url": "https://example.com/products",
            "browser_type": "chromium",
            "headless": True,
            "viewport": {"width": 1280, "height": 720},
            "steps": [
                {"action": "navigate", "params": {"url": "https://example.com/products"}},
                {"action": "fill", "params": {"selector": "#search-input", "value": "iPhone 15"}},
                {"action": "click", "params": {"selector": "#search-btn"}},
                {"action": "wait_for", "params": {"selector": ".product-list", "timeout": 3000}},
                {"action": "click", "params": {"selector": "#filter-price"}},
                {"action": "screenshot", "params": {}}
            ],
            "assertions": [
                {"type": "element_visible", "expected": ".product-list"},
                {"type": "element_count", "expected": "5"}
            ],
            "priority": "P1",
            "status": "active",
            "tags": ["商品", "搜索"],
            "screenshot_enabled": True,
            "full_page_screenshot": False,
            "record_video": False
        },
        {
            "title": "购物车结算流程",
            "description": "验证完整的购物车到结算流程",
            "engine": "playwright",
            "target_url": "https://example.com/cart",
            "browser_type": "chromium",
            "headless": True,
            "viewport": {"width": 1280, "height": 720},
            "steps": [
                {"action": "navigate", "params": {"url": "https://example.com/cart"}},
                {"action": "click", "params": {"selector": "#checkout-btn"}},
                {"action": "wait_for", "params": {"selector": "#payment-form", "timeout": 5000}},
                {"action": "fill", "params": {"selector": "#card-number", "value": "4111111111111111"}},
                {"action": "click", "params": {"selector": "#confirm-payment"}},
                {"action": "wait_for", "params": {"selector": ".order-success", "timeout": 10000}}
            ],
            "assertions": [
                {"type": "text_exists", "expected": "订单提交成功"},
                {"type": "url_contains", "expected": "order-success"}
            ],
            "priority": "P0",
            "status": "active",
            "tags": ["购物车", "支付", "核心链路"],
            "screenshot_enabled": True,
            "full_page_screenshot": True,
            "record_video": False
        }
    ]

    web_ids = []
    for wc in web_cases:
        r = requests.post(WEBCASES, headers=headers, json=wc, timeout=30)
        d = safe_json(r)
        if r.status_code in (200, 201):
            wid = d.get("id")
            web_ids.append(wid)
            print(f"  Web case created: #{wid} - {wc['title']}")
        else:
            print(f"  Web case FAILED: {r.status_code} - {d}")

    # ========== 创建性能测试用例 ==========
    perf_cases = [
        {
            "name": "首页加载性能基准测试",
            "target_url": "https://example.com/",
            "method": "GET",
            "headers": {"Accept": "text/html"},
            "test_type": "baseline",
            "users": 50,
            "spawn_rate": 5,
            "duration": 30,
            "max_avg_response_time": 500,
            "max_p95_response_time": 1000,
            "max_failure_rate": 0.01,
            "status": "active",
            "description": "首页在50并发下的响应时间基准测试"
        },
        {
            "name": "订单API阶梯压力测试",
            "target_url": "https://api.example.com/orders",
            "method": "POST",
            "headers": {"Content-Type": "application/json", "Authorization": "Bearer mock-token"},
            "body": {"product_id": 123, "quantity": 1},
            "test_type": "ramp",
            "users": 100,
            "spawn_rate": 10,
            "duration": 60,
            "ramp_step_users": 20,
            "ramp_step_duration": 10,
            "max_avg_response_time": 800,
            "max_p95_response_time": 1500,
            "max_failure_rate": 0.05,
            "status": "active",
            "description": "订单接口阶梯递增压测，找到性能拐点"
        },
        {
            "name": "混合场景高并发测试",
            "target_url": "https://api.example.com/",
            "method": "GET",
            "headers": {"Accept": "application/json"},
            "test_type": "mixed",
            "users": 200,
            "spawn_rate": 20,
            "duration": 120,
            "mixed_scenarios": [
                {"url": "https://api.example.com/products", "method": "GET", "headers": {}, "body": None, "weight": 60},
                {"url": "https://api.example.com/cart", "method": "GET", "headers": {}, "body": None, "weight": 25},
                {"url": "https://api.example.com/orders", "method": "POST", "headers": {"Content-Type": "application/json"}, "body": {"product_id": 1}, "weight": 15}
            ],
            "max_avg_response_time": 1000,
            "max_p95_response_time": 2000,
            "max_failure_rate": 0.02,
            "status": "active",
            "description": "混合场景：浏览60%、购物车25%、下单15%"
        }
    ]

    perf_ids = []
    for pc in perf_cases:
        r = requests.post(PERF, headers=headers, json=pc, timeout=30)
        d = safe_json(r)
        if r.status_code in (200, 201):
            pid = d.get("id")
            perf_ids.append(pid)
            print(f"  Perf case created: #{pid} - {pc['name']}")
        else:
            print(f"  Perf case FAILED: {r.status_code} - {d}")

    # ========== 执行 Web 测试用例 ==========
    for wid in web_ids:
        exec_url = f"{WEBCASES}{wid}/debug/"
        r = requests.post(exec_url, headers=headers, timeout=120)
        d = safe_json(r)
        if r.status_code in (200, 201):
            print(f"  Web execute #{wid}: {d.get('passed')} | duration={d.get('duration')}s")
        else:
            print(f"  Web execute #{wid} FAILED: {r.status_code} - {d}")
        time.sleep(2)

    # ========== 执行性能测试用例 ==========
    for pid in perf_ids:
        r = requests.post(f"{PERF}execute/", headers=headers, json={"test_case_id": pid}, timeout=60)
        d = safe_json(r)
        if r.status_code in (200, 201):
            print(f"  Perf execute #{pid}: status={d.get('status')} | users={d.get('users')}")
        else:
            print(f"  Perf execute #{pid} FAILED: {r.status_code} - {d}")
        time.sleep(1)

    # ========== 验证数据 ==========
    print("\n--- Final Verify ---")
    r_web = requests.get(WEBCASES, headers=headers, timeout=30)
    d_web = safe_json(r_web)
    web_list = d_web if isinstance(d_web, list) else d_web.get("results", [])
    print(f"Web cases: {len(web_list)}")

    r_perf = requests.get(PERF, headers=headers, timeout=30)
    d_perf = safe_json(r_perf)
    perf_list = d_perf if isinstance(d_perf, list) else d_perf.get("results", [])
    print(f"Perf cases: {len(perf_list)}")

    # Web executions
    r_we = requests.get(f"{WEBCASES}executions/", headers=headers, timeout=30)
    d_we = safe_json(r_we)
    if d_we:
        we_list = d_we if isinstance(d_we, list) else d_we.get("results", [])
        print(f"Web executions: {len(we_list)}")
    else:
        print(f"Web executions query: {r_we.status_code}")

    # Perf executions
    r_pe = requests.get(f"{PERF}executions/", headers=headers, timeout=30)
    d_pe = safe_json(r_pe)
    if d_pe:
        pe_list = d_pe if isinstance(d_pe, list) else d_pe.get("results", [])
        print(f"Perf executions: {len(pe_list)}")
    else:
        print(f"Perf executions query: {r_pe.status_code}")

    print("\nDONE!")

if __name__ == "__main__":
    main()
