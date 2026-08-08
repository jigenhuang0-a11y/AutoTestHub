# -*- coding: utf-8 -*-
"""
安全链路完整验证脚本

验证流程：
1. 安全代码 -> 扫描通过 -> 沙箱执行 -> 审计记录
2. 危险代码(eval) -> 扫描拦截 -> 拒绝执行 -> 审计记录
3. 审计存储查询

运行方式：
  cd agent-harness/backend
  python -m app.core.test_safety_chain
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.code_safety import CodeSafetyChecker, SafetyLevel
from app.core.audit_store import AuditStore


def test_safety_checker():
    """测试安全检查器"""
    print("=" * 60)
    print("[Test 1] Code Safety Checker")
    print("=" * 60)

    checker = CodeSafetyChecker(strict_mode=True)

    # Case 1: Safe code
    safe_code = '''
def add(a, b):
    """simple add function"""
    return a + b

result = add(1, 2)
print(f"Result: {result}")
'''
    report = checker.scan(safe_code)
    print(f"\nSafe code test:")
    print(f"  Level: {report.level.value}")
    print(f"  Passed: {report.passed}")
    print(f"  Summary: {report.summary()}")
    assert report.level == SafetyLevel.SAFE
    assert report.passed
    print("  [PASS]")

    # Case 2: Network code (warning, but still allowed)
    network_code = '''
import requests
def test_api():
    response = requests.get("https://api.example.com/health")
    assert response.status_code == 200
    return response.json()

test_api()
'''
    report = checker.scan(network_code)
    print(f"\nNetwork code test:")
    print(f"  Level: {report.level.value}")
    print(f"  Passed: {report.passed}")
    print(f"  Summary: {report.summary()}")
    assert report.level == SafetyLevel.WARNING
    assert report.passed
    print("  [PASS] (warning -> allowed, audit logged)")

    # Case 3: eval (dangerous)
    dangerous_code = '''
user_input = "os.system('rm -rf /')"
eval(user_input)
'''
    report = checker.scan(dangerous_code)
    print(f"\nDangerous code test (eval):")
    print(f"  Level: {report.level.value}")
    print(f"  Passed: {report.passed}")
    print(f"  Summary: {report.summary()}")
    for issue in report.issues:
        print(f"  Line {issue.line}: [{issue.severity}] {issue.explanation}")
    assert report.level == SafetyLevel.DANGEROUS
    assert not report.passed
    print("  [PASS] Correctly blocked")

    # Case 4: os.system + subprocess
    system_code = '''
import os
os.system("python --version")

import subprocess
result = subprocess.run(["echo", "hello"], shell=True)
'''
    report = checker.scan(system_code)
    print(f"\nHigh-risk code test (os.system + shell=True):")
    print(f"  Level: {report.level.value}")
    print(f"  Passed: {report.passed}")
    print(f"  Issues: {len(report.issues)} found")
    assert not report.passed
    print("  [PASS] Correctly blocked")


def test_audit_store():
    """测试审计持久化存储"""
    print("\n" + "=" * 60)
    print("[Test 2] Audit Persistence Store")
    print("=" * 60)

    import tempfile
    test_db = os.path.join(tempfile.gettempdir(), "test_audit_chain.db")

    store = AuditStore(db_path=test_db)

    # Write safety scan record
    safe_code = "def test(): return True\ntest()"
    checker = CodeSafetyChecker(strict_mode=True)
    safe_report = checker.scan(safe_code)

    audit_id = store.write_safety_report(
        task_id="test-task-001",
        user_id="test_user",
        team_id="test_team",
        code=safe_code,
        report=safe_report,
    )
    print(f"\nWrite safety scan audit: id={audit_id}")
    assert audit_id > 0
    print("  [PASS] Write success")

    # Write sandbox execution record
    audit_id2 = store.write_sandbox_result(
        task_id="test-task-001",
        user_id="test_user",
        team_id="test_team",
        code_hash=safe_report.code_hash,
        status="success",
        duration_ms=125,
        stdout="test() executed OK\n",
        stderr="",
        safety_level="safe",
    )
    print(f"Write sandbox exec audit: id={audit_id2}")
    assert audit_id2 > 0
    print("  [PASS] Write success")

    # Write workflow event
    store.write_workflow_event(
        task_id="test-task-001",
        user_id="test_user",
        team_id="test_team",
        stage="plan",
        status="start",
        message="Workflow started for testing",
    )
    print("  [PASS] Workflow event written")

    # Query stats
    stats = store.get_stats(team_id="test_team", days=7)
    print(f"\nAudit Stats:")
    print(f"  Total events: {stats['total_events']}")
    print(f"  Safety scans: {stats['safety_scans']}")
    print(f"  Safety passed: {stats['safety_passed']}")
    print(f"  Safety blocked: {stats['safety_blocked']}")
    assert stats['total_events'] >= 3
    print("  [PASS] Stats query success")

    # Query events
    events = store.get_recent_events(team_id="test_team", limit=10)
    print(f"\nRecent events: {len(events)} records")
    for e in events:
        print(f"  [{e['event_type']}] {e['message'][:60]}")

    # Query trend
    trend = store.get_safety_trend(team_id="test_team", days=7)
    print(f"\nSafety trend: {len(trend['dates'])} days")

    # Query risk distribution
    risk = store.get_risk_distribution(team_id="test_team", days=7)
    print(f"Risk distribution: {risk}")

    # Cleanup
    store.cleanup_old_records(retention_days=0)
    print("\n  [PASS] Audit cleanup done")

    # Remove test DB
    try:
        os.remove(test_db)
        for suffix in ["-wal", "-shm"]:
            if os.path.exists(test_db + suffix):
                os.remove(test_db + suffix)
    except Exception:
        pass

    print("\n" + "=" * 60)
    print("[ALL PASS] Safety Chain Verified!")
    print("=" * 60)
    print("""
Chain Summary:
  1. AI generates code -> CodeSafetyChecker.scan() -> safe/warning/dangerous
  2. safe     -> sandbox execute -> record to AuditStore
  3. warning  -> mark & allow   -> record to AuditStore
  4. dangerous -> reject         -> record to AuditStore
  5. Audit Dashboard -> /api/agent/audit/* -> visualize all records
""")


if __name__ == "__main__":
    test_safety_checker()
    test_audit_store()
