#!/usr/bin/env python3
"""AutoTestHub 全维度端到端测试 — 覆盖 14 个模块"""
import requests, json, sys, time

BASE_URL = "http://localhost:8000"
TOKEN = None
REFRESH_TOKEN = None
TEST_CASE_ID = None
TEST_SUITE_ID = None
PERF_TEST_ID = None
EXECUTION_ID = None
KB_ID = None
DOC_ID = None
TIMEOUT = 30

results = {"pass": 0, "fail": 0, "skip": 0, "total": 0}


def header():
    h = {"Content-Type": "application/json"}
    if TOKEN:
        h["Authorization"] = f"Bearer {TOKEN}"
    return h


def get_json(resp):
    try:
        return resp.json()
    except Exception:
        return {}


def check(name, resp, status_ok=(200, 201, 204)):
    results["total"] += 1
    ok = resp.status_code in (status_ok if isinstance(status_ok, tuple) else (status_ok,))
    symbol = "✅" if ok else "❌"
    detail = f"(HTTP {resp.status_code})" if ok else f"(HTTP {resp.status_code}, expected {status_ok})"
    print(f"  {symbol} {name} {detail}")
    if not ok:
        try:
            print(f"     Body: {resp.text[:200]}")
        except Exception:
            pass
    results["pass" if ok else "fail"] += 1
    return ok, resp


def skip(name, reason=""):
    results["total"] += 1
    results["skip"] += 1
    print(f"  ⏭️  {name} — {reason}")


# ================================================================
# 1. 认证 (accounts)
# ================================================================
def test_auth():
    global TOKEN, REFRESH_TOKEN
    print("\n" + "=" * 60)
    print("🔐 [1/14] 认证 (accounts)")
    print("=" * 60)

    ok, resp = check("登录", requests.post(
        f"{BASE_URL}/api/auth/login/",
        json={"username": "admin", "password": "admin123"},
        headers={"Content-Type": "application/json"},
        timeout=TIMEOUT,
    ), (200, 400))

    if not ok:
        ok2, resp2 = check("注册", requests.post(
            f"{BASE_URL}/api/auth/register/",
            json={"username": "tester", "email": "tester@test.com", "password": "Admin123!", "password2": "Admin123!"},
            headers={"Content-Type": "application/json"},
            timeout=TIMEOUT,
        ), (200, 201, 400))
        if ok2:
            data = get_json(resp2)
            TOKEN = data.get("access") or data.get("token")
        else:
            skip("Token获取", "注册/登录均失败")
            return
        ok3, resp3 = check("登录(重试)", requests.post(
            f"{BASE_URL}/api/auth/login/",
            json={"username": "tester", "password": "Admin123!"},
            headers={"Content-Type": "application/json"},
            timeout=TIMEOUT,
        ))
        if ok3:
            data = get_json(resp3)
            TOKEN = data.get("access") or data.get("token")
            REFRESH_TOKEN = data.get("refresh")
    else:
        data = get_json(resp)
        TOKEN = data.get("access") or data.get("token")
        REFRESH_TOKEN = data.get("refresh")

    if not TOKEN:
        skip("Token获取", "无法获取JWT")
        return

    check("用户资料", requests.get(f"{BASE_URL}/api/auth/profile/", headers=header(), timeout=TIMEOUT))
    check("Token刷新", requests.post(f"{BASE_URL}/api/auth/token/refresh/", json={"refresh": REFRESH_TOKEN}, headers=header(), timeout=TIMEOUT), (200, 400))


# ================================================================
# 2. AI模型配置 (ai_evaluator)
# ================================================================
def test_ai_models():
    print("\n" + "=" * 60)
    print("🤖 [2/14] AI模型配置 (ai_evaluator)")
    print("=" * 60)

    ok, resp = check("模型列表", requests.get(f"{BASE_URL}/api/ai-evaluator/models/", headers=header(), timeout=TIMEOUT))
    if ok:
        data = get_json(resp)
        models = data if isinstance(data, list) else data.get("results", [])
        if models:
            print(f"     {len(models)} 个模型配置: {[m.get('name','?') for m in models[:5]]}")

    check("评测任务列表", requests.get(f"{BASE_URL}/api/ai-evaluator/tasks/", headers=header(), timeout=TIMEOUT))


# ================================================================
# 3. 接口测试用例 (testcases)
# ================================================================
def test_testcases():
    global TEST_CASE_ID
    print("\n" + "=" * 60)
    print("📝 [3/14] 接口测试用例 (testcases)")
    print("=" * 60)

    ok, resp = check("用例列表", requests.get(f"{BASE_URL}/api/testcases/", headers=header(), timeout=TIMEOUT))
    if ok:
        data = get_json(resp)
        existing = data if isinstance(data, list) else data.get("results", [])
        print(f"     已有 {len(existing)} 个用例")

    ok, resp = check("创建用例", requests.post(f"{BASE_URL}/api/testcases/", json={
        "title": "[E2E测试] 百度搜索接口",
        "description": "自动生成的端到端测试用例",
        "api_endpoint": "https://www.baidu.com/s",
        "method": "GET",
        "headers": {"User-Agent": "AutoTestHub/1.0"},
        "params": {"wd": "test"},
        "priority": "P2",
        "status": "draft",
        "expected_response": {"status_code": 200},
        "assertion_rules": [{"type": "status_code", "expected": 200}],
    }, headers=header(), timeout=TIMEOUT))
    if ok:
        data = get_json(resp)
        TEST_CASE_ID = data.get("id")
        print(f"     用例ID: {TEST_CASE_ID}")

    if TEST_CASE_ID:
        check("查看用例详情", requests.get(f"{BASE_URL}/api/testcases/{TEST_CASE_ID}/", headers=header(), timeout=TIMEOUT))
        check("更新用例", requests.patch(f"{BASE_URL}/api/testcases/{TEST_CASE_ID}/", json={"status": "active", "priority": "P1"}, headers=header(), timeout=TIMEOUT))


# ================================================================
# 4. 测试套件 (testsuites)
# ================================================================
def test_testsuites():
    global TEST_SUITE_ID
    print("\n" + "=" * 60)
    print("📦 [4/14] 测试套件 (testsuites)")
    print("=" * 60)

    check("套件列表", requests.get(f"{BASE_URL}/api/testsuites/", headers=header(), timeout=TIMEOUT))
    ok, resp = check("创建套件", requests.post(f"{BASE_URL}/api/testsuites/", json={
        "name": "[E2E测试] 全模块冒烟套件",
        "description": "自动创建的端到端测试套件",
    }, headers=header(), timeout=TIMEOUT))
    if ok:
        data = get_json(resp)
        TEST_SUITE_ID = data.get("id")
        print(f"     套件ID: {TEST_SUITE_ID}")


# ================================================================
# 5. Web UI 测试用例 (web_testcases)
# ================================================================
def test_web_testcases():
    print("\n" + "=" * 60)
    print("🌐 [5/14] Web UI 测试 (web_testcases)")
    print("=" * 60)

    check("Web用例列表", requests.get(f"{BASE_URL}/api/web-testcases/", headers=header(), timeout=TIMEOUT))
    check("创建Web用例", requests.post(f"{BASE_URL}/api/web-testcases/", json={
        "title": "[E2E测试] 百度首页加载",
        "url": "https://www.baidu.com",
        "steps": [{"action": "navigate", "url": "https://www.baidu.com"}, {"action": "wait", "selector": "#kw", "timeout": 5000}],
        "priority": "P2",
    }, headers=header(), timeout=TIMEOUT))
    check("Web执行列表", requests.get(f"{BASE_URL}/api/web-testcases/executions/", headers=header(), timeout=TIMEOUT))


# ================================================================
# 6. 性能测试 (performance)
# ================================================================
def test_performance():
    global PERF_TEST_ID
    print("\n" + "=" * 60)
    print("⚡ [6/14] 性能测试 (performance)")
    print("=" * 60)

    check("性能用例列表", requests.get(f"{BASE_URL}/api/performance/", headers=header(), timeout=TIMEOUT))
    ok, resp = check("创建性能用例", requests.post(f"{BASE_URL}/api/performance/", json={
        "name": "[E2E测试] 压测用例",
        "target_url": "https://www.baidu.com",
        "method": "GET",
        "test_type": "baseline",
        "users": 5,
        "duration": 10,
        "qps_threshold": 5,
        "p95_threshold": 2000,
    }, headers=header(), timeout=TIMEOUT))
    if ok:
        data = get_json(resp)
        PERF_TEST_ID = data.get("id")
        print(f"     性能用例ID: {PERF_TEST_ID}")
    check("执行列表", requests.get(f"{BASE_URL}/api/performance/executions/", headers=header(), timeout=TIMEOUT))


# ================================================================
# 7. 测试执行引擎 (execution)
# ================================================================
def test_execution():
    global EXECUTION_ID
    print("\n" + "=" * 60)
    print("🚀 [7/14] 测试执行引擎 (execution)")
    print("=" * 60)

    check("执行列表", requests.get(f"{BASE_URL}/api/execution/", headers=header(), timeout=TIMEOUT))
    if TEST_CASE_ID:
        ok, resp = check("触发执行", requests.post(f"{BASE_URL}/api/execution/", json={
            "test_case_ids": [TEST_CASE_ID],
            "trigger_type": "manual",
            "environment": "test",
        }, headers=header(), timeout=TIMEOUT))
        if ok:
            data = get_json(resp)
            EXECUTION_ID = data.get("id")
            print(f"     执行ID: {EXECUTION_ID}")
    for ep in ["stats/", "stats/dashboard/", "stats/error-trend/", "stats/token-trend/"]:
        check(f"统计: {ep}", requests.get(f"{BASE_URL}/api/execution/{ep}", headers=header(), timeout=TIMEOUT), (200, 400, 404))


# ================================================================
# 8. 知识库问答 (knowledge_base)
# ================================================================
def test_knowledge_base():
    global KB_ID, DOC_ID
    print("\n" + "=" * 60)
    print("📚 [8/14] 知识库问答 (knowledge_base)")
    print("=" * 60)

    check("知识库列表", requests.get(f"{BASE_URL}/api/knowledge/knowledge-bases/", headers=header(), timeout=TIMEOUT))
    if ok:
        data = get_json(resp)
        kbs = data.get("results", []) if isinstance(data, dict) else []
        if kbs:
            KB_ID = kbs[0].get("id")
            print(f"     使用知识库ID: {KB_ID}")
    check("文档列表", requests.get(f"{BASE_URL}/api/knowledge/documents/", headers=header(), timeout=TIMEOUT))
    if KB_ID:
        print(f"     流式问答(SSE) — kb_id={KB_ID}...")
        try:
            resp = requests.post(f"{BASE_URL}/api/knowledge/knowledge-bases/{KB_ID}/ask_stream/", json={"question": "AI评测工程师面试有哪些常见问题?", "stream": True}, headers=header(), timeout=60, stream=True)
            got_answer = False
            for line in resp.iter_lines(decode_unicode=True):
                if line and line.startswith("data:"):
                    ds = line[5:].strip()
                    if ds == "[DONE]": break
                    try:
                        chunk = json.loads(ds)
                        if chunk.get("type") == "content" and chunk.get("content"):
                            if not got_answer:
                                got_answer = True
                                print(f"     收到回答: {chunk['content'][:80]}...")
                    except json.JSONDecodeError:
                        pass
            results["total"] += 1
            if got_answer:
                results["pass"] += 1
                print("  ✅ 流式问答  (SSE 正常)")
            else:
                results["fail"] += 1
                print("  ❌ 流式问答  (未收到回答)")
        except Exception as e:
            results["total"] += 1
            results["fail"] += 1
            print(f"  ❌ 流式问答  (异常: {e})")


# ================================================================
# 9. 数据工厂 (data_factory)
# ================================================================
def test_data_factory():
    print("\n" + "=" * 60)
    print("🏭 [9/14] 数据工厂 (data_factory)")
    print("=" * 60)
    for ep in ["datasets/", "templates/", "preset-templates/", "usage-logs/"]:
        check(f"数据工厂: {ep}", requests.get(f"{BASE_URL}/api/data-factory/{ep}", headers=header(), timeout=TIMEOUT))


# ================================================================
# 10. 质量检查 (quality_checker)
# ================================================================
def test_quality_checker():
    print("\n" + "=" * 60)
    print("✅ [10/14] 质量检查 (quality_checker)")
    print("=" * 60)
    check("检查任务列表", requests.get(f"{BASE_URL}/api/quality-checker/tasks/", headers=header(), timeout=TIMEOUT))
    check("质量标准列表", requests.get(f"{BASE_URL}/api/quality-checker/standards/", headers=header(), timeout=TIMEOUT))


# ================================================================
# 11. AI评测器 (ai_evaluator)
# ================================================================
def test_ai_evaluator():
    print("\n" + "=" * 60)
    print("📊 [11/14] AI评测器 (ai_evaluator)")
    print("=" * 60)
    check("评测任务列表", requests.get(f"{BASE_URL}/api/ai-evaluator/tasks/", headers=header(), timeout=TIMEOUT))
    ok, resp = check("创建评测任务", requests.post(f"{BASE_URL}/api/ai-evaluator/tasks/", json={
        "name": "[E2E测试] 模型回答质量评测",
        "description": "测试多模型生成质量",
        "questions": [{"question": "什么是软件测试中的等价类划分？"}, {"question": "解释一下边界值分析。"}],
        "evaluation_criteria": {"accuracy": 0.3, "completeness": 0.25, "clarity": 0.2, "relevance": 0.15, "efficiency": 0.1},
    }, headers=header(), timeout=TIMEOUT), (200, 201, 400))
    if not ok:
        print("     (可能需要有效的模型配置)")


# ================================================================
# 12. Agent网关 + 自愈 (agent_gateway)
# ================================================================
def test_agent():
    print("\n" + "=" * 60)
    print("🤖 [12/14] Agent网关 + 自愈 (agent_gateway)")
    print("=" * 60)
    check("Agent任务列表", requests.get(f"{BASE_URL}/api/agent/tasks/", headers=header(), timeout=TIMEOUT))
    for ep in ["stats/", "history/"]:
        check(f"自愈: {ep}", requests.get(f"{BASE_URL}/api/agent/self-healing/{ep}", headers=header(), timeout=TIMEOUT))


# ================================================================
# 13. 报告模块 (reports)
# ================================================================
def test_reports():
    print("\n" + "=" * 60)
    print("📄 [13/14] 报告模块 (reports)")
    print("=" * 60)
    check("报告列表", requests.get(f"{BASE_URL}/api/reports/", headers=header(), timeout=TIMEOUT))


# ================================================================
# 14. 清理 & 管理后台
# ================================================================
def test_cleanup():
    print("\n" + "=" * 60)
    print("🧹 [14/14] 清理 & 管理后台")
    print("=" * 60)
    check("Django Admin", requests.get(f"{BASE_URL}/admin/", timeout=TIMEOUT), (200, 302, 404))
    for endpoint, obj_id, label in [
        (f"/api/performance/{PERF_TEST_ID}/", PERF_TEST_ID, "性能用例"),
        (f"/api/testcases/{TEST_CASE_ID}/", TEST_CASE_ID, "测试用例"),
        (f"/api/testsuites/{TEST_SUITE_ID}/", TEST_SUITE_ID, "测试套件"),
    ]:
        if obj_id:
            ok, resp = check(f"清理{label}", requests.delete(f"{BASE_URL}{endpoint}", headers=header(), timeout=TIMEOUT), (200, 204, 404))
            if not ok and resp.status_code == 404:
                print(f"     (资源已被删除或不存在，跳过)")


# ================================================================
# 主流程
# ================================================================
def main():
    print("""
╔══════════════════════════════════════════════════════════════╗
║       🚀 AutoTestHub — 全维度端到端测试                        ║
║       覆盖 14 个模块，验证各功能核心链路                       ║
╚══════════════════════════════════════════════════════════════╝
    """)
    start_time = time.time()
    try:
        requests.get(BASE_URL, timeout=5)
    except requests.ConnectionError:
        print(f"\n❌ 无法连接到 {BASE_URL}，请确认 gunicorn 已启动！")
        sys.exit(1)

    test_auth()
    test_ai_models()
    test_testcases()
    test_testsuites()
    test_web_testcases()
    test_performance()
    test_execution()
    test_knowledge_base()
    test_data_factory()
    test_quality_checker()
    test_ai_evaluator()
    test_agent()
    test_reports()
    test_cleanup()

    elapsed = time.time() - start_time
    print("\n" + "=" * 50)
    pct = results["pass"] / results["total"] * 100 if results["total"] else 0
    print(f"📋 总计: {results['total']} | ✅ {results['pass']} ❌ {results['fail']} ⏭️ {results['skip']}")
    print(f"📊 通过率: {pct:.1f}%")
    grade = "S" if pct >= 95 else "A" if pct >= 85 else "B" if pct >= 70 else "C" if pct >= 50 else "D"
    print(f"🎯 综合: {grade} 💪")
    print(f"⏱️  耗时: {elapsed:.1f}s")
    print("=" * 50)


if __name__ == "__main__":
    main()
