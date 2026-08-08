# -*- coding: utf-8 -*-
import requests, json, time

BASE = "http://8.163.95.60"
LOGIN = f"{BASE}/api/auth/login/"
TESTCASES = f"{BASE}/api/testcases/"
EXECUTIONS = f"{BASE}/api/execution/"
SUITES = f"{BASE}/api/testsuites/"

def get_token():
    r = requests.post(LOGIN, json={"username":"admin","password":"admin123"}, timeout=30)
    if r.status_code != 200:
        print(f"Login failed: {r.status_code}")
        return None
    d = r.json()
    return d.get("access", d.get("token",""))

def safe_json(resp):
    try:
        return resp.json()
    except Exception:
        return None

def main():
    token = get_token()
    if not token:
        print("No token")
        return
    print(f"Token OK: {token[:30]}...")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # 1. Get all cases
    r = requests.get(TESTCASES, headers=headers, timeout=30)
    data = safe_json(r)
    if data is None:
        print(f"GET /api/testcases/ failed: {r.status_code}")
        print(r.text[:300])
        return
    cases = data if isinstance(data, list) else data.get("results", [])
    print(f"Cases: {len(cases)}")

    # 2. Activate drafts
    activated = 0
    for c in cases:
        if c.get("status") == "draft":
            patch_r = requests.patch(f"{TESTCASES}{c['id']}/", headers=headers, json={"status":"active"}, timeout=30)
            if patch_r.status_code in (200, 201):
                activated += 1
            else:
                print(f"  Activate #{c['id']} failed: {patch_r.status_code}")
    print(f"Activated: {activated}")
    time.sleep(1)

    # 3. Re-fetch active cases
    r2 = requests.get(TESTCASES, headers=headers, timeout=30)
    data2 = safe_json(r2)
    cases2 = data2 if isinstance(data2, list) else data2.get("results", [])
    active_ids = [c["id"] for c in cases2 if c.get("status") == "active"]
    print(f"Active IDs: {active_ids}")

    if not active_ids:
        print("No active cases to execute")
        return

    # 4. Execute cases in batches
    for i in range(0, len(active_ids), 5):
        batch = active_ids[i:i+5]
        exec_r = requests.post(EXECUTIONS, headers=headers, json={
            "test_case_ids": batch,
            "trigger_type": "manual_case"
        }, timeout=120)
        print(f"  Execute batch {i//5+1}: HTTP {exec_r.status_code}")
        if exec_r.status_code in (200, 201):
            d = safe_json(exec_r)
            if d:
                print(f"    Result: status={d.get('status')}, P={d.get('passed_count')}, F={d.get('failed_count')}")
        else:
            print(f"    Body: {exec_r.text[:200]}")
        time.sleep(1)

    # 5. Create suite and execute
    suite_r = requests.post(SUITES, headers=headers, json={
        "name": "核心链路回归套件",
        "description": "覆盖登录、商品、订单、支付的核心链路",
        "test_case_ids": active_ids[:6],
        "environment": "staging",
        "trigger_type": "manual"
    }, timeout=60)
    print(f"Suite create: {suite_r.status_code}")
    if suite_r.status_code in (200, 201):
        suite = safe_json(suite_r)
        if suite and "id" in suite:
            sid = suite["id"]
            exec_s = requests.post(f"{SUITES}{sid}/execute/", headers=headers, timeout=120)
            print(f"  Suite execute: {exec_s.status_code}")
            if exec_s.status_code not in (200, 201):
                print(f"  Body: {exec_s.text[:200]}")

    # 6. Verify executions
    print("\n--- Verify ---")
    r3 = requests.get(EXECUTIONS, headers=headers, timeout=30)
    data3 = safe_json(r3)
    if data3 is None:
        print(f"GET executions failed: {r3.status_code}")
        print(r3.text[:300])
        return
    execs = data3 if isinstance(data3, list) else data3.get("results", [])
    print(f"Total executions: {len(execs)}")
    for e in execs:
        print(f"  #{e.get('id')} | {e.get('status')} | P:{e.get('passed_count')} F:{e.get('failed_count')} | {str(e.get('started_at',''))[:10]}")
    print("\nDONE")

if __name__ == "__main__":
    main()
