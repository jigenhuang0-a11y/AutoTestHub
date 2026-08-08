#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 测试平台 - 全功能自动化测试脚本
目标：跑通核心功能、造真实数据、记录问题
服务器: http://8.163.95.60
"""

import requests
import json
import time
from datetime import datetime, timedelta

BASE_URL = "http://8.163.95.60"
API_PREFIX = f"{BASE_URL}/api"
TIMEOUT = 30

# 全局状态记录
results = {
    "start_time": datetime.now().isoformat(),
    "modules": {},
    "errors": [],
    "data_created": {},
}

headers = {"Content-Type": "application/json"}


def log_test(module, endpoint, method, status, detail="", error=None):
    """记录测试结果"""
    if module not in results["modules"]:
        results["modules"][module] = {"tests": [], "passed": 0, "failed": 0}
    
    test = {
        "endpoint": endpoint,
        "method": method,
        "status": status,
        "detail": detail,
        "error": error,
        "time": datetime.now().isoformat(),
    }
    results["modules"][module]["tests"].append(test)
    if status == "PASS":
        results["modules"][module]["passed"] += 1
    else:
        results["modules"][module]["failed"] += 1
        if error:
            results["errors"].append(f"[{module}] {endpoint}: {error}")
    
    icon = "" if status == "PASS" else ""
    print(f"  {icon} {method} {endpoint} - {status}")
    if error:
        print(f"     Error: {error}")


def safe_request(method, url, **kwargs):
    """安全请求，统一捕获异常"""
    try:
        resp = requests.request(method, url, timeout=TIMEOUT, **kwargs)
        return resp
    except Exception as e:
        return None, str(e)


# ==================== 1. 认证模块 ====================
def test_auth():
    print("\n# [1/11] 认证模块测试")
    module = "auth"
    
    # 1.1 登录
    resp = requests.post(
        f"{API_PREFIX}/auth/login/",
        json={"username": "admin", "password": "admin123"},
        headers=headers,
        timeout=TIMEOUT
    )
    if resp.status_code == 200:
        data = resp.json()
        token = data.get("access", "")
        if token:
            headers["Authorization"] = f"Bearer {token}"
            log_test(module, "/auth/login/", "POST", "PASS", f"Token获取成功")
            results["data_created"]["token"] = token[:20] + "..."
        else:
            log_test(module, "/auth/login/", "POST", "FAIL", "", "响应无token字段")
    else:
        log_test(module, "/auth/login/", "POST", "FAIL", "", f"HTTP {resp.status_code}: {resp.text[:200]}")
        return False
    
    # 1.2 获取用户信息
    resp = requests.get(f"{API_PREFIX}/auth/profile/", headers=headers, timeout=TIMEOUT)
    log_test(module, "/auth/profile/", "GET", "PASS" if resp.status_code == 200 else "FAIL",
             detail="", error=None if resp.status_code == 200 else f"HTTP {resp.status_code}")
    
    return True


# ==================== 2. 用例管理 - API测试 ====================
def test_testcases():
    print("\n [2/11] API 用例管理测试")
    module = "testcases"
    
    # 2.1 创建 API 测试用例
    testcase = {
        "name": "订单创建接口测试",
        "method": "POST",
        "url": "https://api.example.com/orders",
        "headers": {"Content-Type": "application/json", "Authorization": "Bearer test-token"},
        "body": json.dumps({"product_id": 123, "quantity": 2, "user_id": 456}),
        "assertions": [
            {"type": "status_code", "expected": 201},
            {"type": "json_path", "path": "$.order_id", "operator": "exists"},
            {"type": "json_path", "path": "$.status", "expected": "created"}
        ],
        "tags": ["订单", "核心链路"],
        "priority": "high",
        "category": "接口测试"
    }
    resp = requests.post(f"{API_PREFIX}/testcases/", json=testcase, headers=headers, timeout=TIMEOUT)
    if resp.status_code in (200, 201):
        data = resp.json()
        tc_id = data.get("id")
        log_test(module, "/testcases/", "POST", "PASS", f"用例ID={tc_id}")
        results["data_created"]["api_testcase_id"] = tc_id
        
        # 2.2 用例列表
        resp = requests.get(f"{API_PREFIX}/testcases/?page=1&page_size=10", headers=headers, timeout=TIMEOUT)
        log_test(module, "/testcases/", "GET", "PASS" if resp.status_code == 200 else "FAIL",
                 error=None if resp.status_code == 200 else f"HTTP {resp.status_code}")
        
        # 2.3 用例详情
        resp = requests.get(f"{API_PREFIX}/testcases/{tc_id}/", headers=headers, timeout=TIMEOUT)
        log_test(module, f"/testcases/{tc_id}/", "GET", "PASS" if resp.status_code == 200 else "FAIL",
                 error=None if resp.status_code == 200 else f"HTTP {resp.status_code}")
    else:
        log_test(module, "/testcases/", "POST", "FAIL", "", f"HTTP {resp.status_code}: {resp.text[:300]}")


# ==================== 3. Web 自动化测试 ====================
def test_web_testcases():
    print("\n [3/11] Web 自动化测试")
    module = "web_testcases"
    
    webcase = {
        "name": "电商登录流程测试",
        "url": "https://example.com/login",
        "steps": [
            {"action": "navigate", "target": "https://example.com/login"},
            {"action": "fill", "target": "#username", "value": "test_user"},
            {"action": "fill", "target": "#password", "value": "test_pass"},
            {"action": "click", "target": "#login-btn"},
            {"action": "wait_for", "target": ".dashboard", "timeout": 5000}
        ],
        "assertions": [
            {"type": "url_contains", "expected": "/dashboard"},
            {"type": "element_exists", "target": ".user-profile"}
        ],
        "tags": ["登录", "Web", "冒烟测试"],
        "priority": "high"
    }
    resp = requests.post(f"{API_PREFIX}/web-testcases/", json=webcase, headers=headers, timeout=TIMEOUT)
    if resp.status_code in (200, 201):
        data = resp.json()
        wc_id = data.get("id")
        log_test(module, "/web-testcases/", "POST", "PASS", f"Web用例ID={wc_id}")
        results["data_created"]["web_testcase_id"] = wc_id
    else:
        log_test(module, "/web-testcases/", "POST", "FAIL", "", f"HTTP {resp.status_code}: {resp.text[:300]}")


# ==================== 4. 测试套件 ====================
def test_testsuites():
    print("\n [4/11] 测试套件管理")
    module = "testsuites"
    
    suite = {
        "name": "核心链路回归测试套件",
        "description": "包含订单、支付、用户核心流程的回归测试",
        "tags": ["回归", "核心链路"],
        "test_cases": [
            {"type": "api", "id": results["data_created"].get("api_testcase_id", 1)}
        ]
    }
    resp = requests.post(f"{API_PREFIX}/testsuites/", json=suite, headers=headers, timeout=TIMEOUT)
    if resp.status_code in (200, 201):
        data = resp.json()
        suite_id = data.get("id")
        log_test(module, "/testsuites/", "POST", "PASS", f"套件ID={suite_id}")
        results["data_created"]["testsuite_id"] = suite_id
        
        # 执行套件
        resp = requests.post(f"{API_PREFIX}/testsuites/{suite_id}/execute/", 
                            json={}, headers=headers, timeout=TIMEOUT)
        log_test(module, f"/testsuites/{suite_id}/execute/", "POST", 
                "PASS" if resp.status_code in (200, 202) else "FAIL",
                error=None if resp.status_code in (200, 202) else f"HTTP {resp.status_code}")
    else:
        log_test(module, "/testsuites/", "POST", "FAIL", "", f"HTTP {resp.status_code}: {resp.text[:300]}")


# ==================== 5. 数据工厂 ====================
def test_data_factory():
    print("\n [5/11] 数据工厂 - LLM评测数据生成")
    module = "data_factory"
    
    # 5.1 生成 LLM 评测数据
    llm_data = {
        "dataset_type": "llm_eval",
        "scenario": "电商平台客服对话场景：用户咨询订单物流状态，要求AI能准确查询订单信息并给出物流追踪结果",
        "record_count": 10,
        "difficulty_distribution": {"easy": 30, "medium": 50, "hard": 20}
    }
    resp = requests.post(f"{API_PREFIX}/data-factory/generate-llm-dataset/",
                        json=llm_data, headers=headers, timeout=120)
    if resp.status_code in (200, 201):
        data = resp.json()
        dataset_id = data.get("dataset_id", data.get("id"))
        log_test(module, "/data-factory/generate-llm-dataset/", "POST", "PASS", 
                f"数据集生成成功 ID={dataset_id}")
        results["data_created"]["llm_dataset_id"] = dataset_id
    else:
        log_test(module, "/data-factory/generate-llm-dataset/", "POST", "FAIL", "",
                f"HTTP {resp.status_code}: {resp.text[:300]}")
    
    # 5.2 数据集列表
    resp = requests.get(f"{API_PREFIX}/data-factory/datasets/", headers=headers, timeout=TIMEOUT)
    log_test(module, "/data-factory/datasets/", "GET", "PASS" if resp.status_code == 200 else "FAIL",
             error=None if resp.status_code == 200 else f"HTTP {resp.status_code}")


# ==================== 6. AI测评师 ====================
def test_ai_evaluator():
    print("\n [6/11] AI 测评师")
    module = "ai_evaluator"
    
    # 6.1 创建测评任务
    eval_task = {
        "name": "DeepSeek-Chat 客服场景评测",
        "model_name": "deepseek-chat",
        "dataset_id": results["data_created"].get("llm_dataset_id", 1),
        "evaluation_config": {
            "metrics": ["accuracy", "fluency", "safety"],
            "sampling_rate": 1.0
        }
    }
    resp = requests.post(f"{API_PREFIX}/ai-evaluator/", json=eval_task, headers=headers, timeout=TIMEOUT)
    if resp.status_code in (200, 201):
        data = resp.json()
        eval_id = data.get("id")
        log_test(module, "/ai-evaluator/", "POST", "PASS", f"测评任务ID={eval_id}")
        results["data_created"]["eval_task_id"] = eval_id
    else:
        log_test(module, "/ai-evaluator/", "POST", "FAIL", "", f"HTTP {resp.status_code}: {resp.text[:300]}")
    
    # 6.2 测评任务列表
    resp = requests.get(f"{API_PREFIX}/ai-evaluator/", headers=headers, timeout=TIMEOUT)
    log_test(module, "/ai-evaluator/", "GET", "PASS" if resp.status_code == 200 else "FAIL",
             error=None if resp.status_code == 200 else f"HTTP {resp.status_code}")


# ==================== 7. 知识库 / AI问答 ====================
def test_knowledge_base():
    print("\n [7/11] 知识库 & AI问答")
    module = "knowledge_base"
    
    # 7.1 创建知识库
    kb = {
        "name": "产品测试规范知识库",
        "description": "包含API测试规范、Web测试标准、性能测试指标等产品测试相关文档",
    }
    resp = requests.post(f"{API_PREFIX}/knowledge/knowledge-bases/", json=kb, headers=headers, timeout=TIMEOUT)
    if resp.status_code in (200, 201):
        data = resp.json()
        kb_id = data.get("id")
        log_test(module, "/knowledge/knowledge-bases/", "POST", "PASS", f"知识库ID={kb_id}")
        results["data_created"]["knowledge_base_id"] = kb_id
    else:
        log_test(module, "/knowledge/knowledge-bases/", "POST", "FAIL", "", f"HTTP {resp.status_code}: {resp.text[:300]}")
    
    # 7.2 AI问答
    qa = {
        "question": "API测试用例应该如何设计断言？",
        "knowledge_base_id": results["data_created"].get("knowledge_base_id", 1)
    }
    resp = requests.post(f"{API_PREFIX}/knowledge/ask/", json=qa, headers=headers, timeout=60)
    log_test(module, "/knowledge/ask/", "POST", "PASS" if resp.status_code == 200 else "FAIL",
             error=None if resp.status_code == 200 else f"HTTP {resp.status_code}")


# ==================== 8. 质量检查 ====================
def test_quality_checker():
    print("\n [8/11] 质量检查")
    module = "quality_checker"
    
    # 8.1 检查 API 用例质量
    check_data = {
        "check_type": "testcase_quality",
        "target_id": results["data_created"].get("api_testcase_id", 1),
        "rules": ["assertion_coverage", "naming_convention", "parameter_completeness"]
    }
    resp = requests.post(f"{API_PREFIX}/quality-checker/check/", json=check_data, headers=headers, timeout=TIMEOUT)
    log_test(module, "/quality-checker/check/", "POST", "PASS" if resp.status_code in (200, 202) else "FAIL",
             error=None if resp.status_code in (200, 202) else f"HTTP {resp.status_code}")
    
    # 8.2 质量检查历史
    resp = requests.get(f"{API_PREFIX}/quality-checker/checks/", headers=headers, timeout=TIMEOUT)
    log_test(module, "/quality-checker/checks/", "GET", "PASS" if resp.status_code == 200 else "FAIL",
             error=None if resp.status_code == 200 else f"HTTP {resp.status_code}")


# ==================== 9. 执行历史 & 数据看板 ====================
def test_execution():
    print("\n [9/11] 执行历史 & 数据看板")
    module = "execution"
    
    # 9.1 执行历史列表
    resp = requests.get(f"{API_PREFIX}/execution/?page=1&page_size=10", headers=headers, timeout=TIMEOUT)
    log_test(module, "/execution/", "GET", "PASS" if resp.status_code == 200 else "FAIL",
             error=None if resp.status_code == 200 else f"HTTP {resp.status_code}")
    
    # 9.2 数据看板统计
    resp = requests.get(f"{API_PREFIX}/execution/stats/dashboard/", headers=headers, timeout=TIMEOUT)
    log_test(module, "/execution/stats/dashboard/", "GET", "PASS" if resp.status_code == 200 else "FAIL",
             error=None if resp.status_code == 200 else f"HTTP {resp.status_code}")
    
    # 9.3 报错趋势
    resp = requests.get(f"{API_PREFIX}/execution/stats/error-trend/?days=7", headers=headers, timeout=TIMEOUT)
    log_test(module, "/execution/stats/error-trend/", "GET", "PASS" if resp.status_code == 200 else "FAIL",
             error=None if resp.status_code == 200 else f"HTTP {resp.status_code}")
    
    # 9.4 Token 消耗趋势
    resp = requests.get(f"{API_PREFIX}/execution/stats/token-trend/?days=7", headers=headers, timeout=TIMEOUT)
    log_test(module, "/execution/stats/token-trend/", "GET", "PASS" if resp.status_code == 200 else "FAIL",
             error=None if resp.status_code == 200 else f"HTTP {resp.status_code}")


# ==================== 10. 模型管理 ====================
def test_model_management():
    print("\n [10/11] 模型管理")
    module = "model_management"
    
    # 10.1 模型列表
    resp = requests.get(f"{API_PREFIX}/ai-evaluator/models/", headers=headers, timeout=TIMEOUT)
    log_test(module, "/ai-evaluator/models/", "GET", "PASS" if resp.status_code == 200 else "FAIL",
             error=None if resp.status_code == 200 else f"HTTP {resp.status_code}")
    
    # 10.2 模型配置（如果存在该端点）
    resp = requests.get(f"{API_PREFIX}/ai-evaluator/configs/", headers=headers, timeout=TIMEOUT)
    if resp.status_code == 200:
        log_test(module, "/ai-evaluator/configs/", "GET", "PASS")
    else:
        log_test(module, "/ai-evaluator/configs/", "GET", "SKIP", detail="端点可能不存在")


# ==================== 11. 技能库 / Agent 网关 ====================
def test_agent_gateway():
    print("\n [11/11] 技能库 / Agent 网关")
    module = "agent_gateway"
    
    # 11.1 技能列表
    resp = requests.get(f"{API_PREFIX}/agent/skills/", headers=headers, timeout=TIMEOUT)
    log_test(module, "/agent/skills/", "GET", "PASS" if resp.status_code == 200 else "FAIL",
             error=None if resp.status_code == 200 else f"HTTP {resp.status_code}")
    
    # 11.2 MCP 工具列表
    resp = requests.get(f"{API_PREFIX}/mcp/tools/", headers=headers, timeout=TIMEOUT)
    log_test(module, "/mcp/tools/", "GET", "PASS" if resp.status_code == 200 else "FAIL",
             error=None if resp.status_code == 200 else f"HTTP {resp.status_code}")


# ==================== 主流程 ====================
def run_all_tests():
    print("=" * 60)
    print(" AI 测试平台 - 全功能自动化测试开始")
    print(f"   服务器: {BASE_URL}")
    print(f"   时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # 1. 认证（必须成功，否则后续无法执行）
    if not test_auth():
        print("\n 认证失败，终止测试")
        return
    
    # 2-11. 各功能模块
    test_testcases()
    test_web_testcases()
    test_testsuites()
    test_data_factory()
    test_ai_evaluator()
    test_knowledge_base()
    test_quality_checker()
    test_execution()
    test_model_management()
    test_agent_gateway()
    
    # 生成报告
    print("\n" + "=" * 60)
    print(" 测试报告")
    print("=" * 60)
    
    total_passed = 0
    total_failed = 0
    for mod_name, mod_data in results["modules"].items():
        passed = mod_data["passed"]
        failed = mod_data["failed"]
        total = passed + failed
        total_passed += passed
        total_failed += failed
        status = "" if failed == 0 else "️"
        print(f"  {status} {mod_name:20s} | 通过: {passed:2d} | 失败: {failed:2d} | 总计: {total:2d}")
    
    print(f"\n   总计: 通过 {total_passed} | 失败 {total_failed} | 成功率 {total_passed/(total_passed+total_failed)*100:.1f}%")
    
    if results["errors"]:
        print(f"\n   错误列表 ({len(results['errors'])} 项):")
        for err in results["errors"]:
            print(f"     - {err}")
    else:
        print("\n   所有测试通过，无错误！")
    
    print(f"\n   创建的数据:")
    for k, v in results["data_created"].items():
        print(f"     - {k}: {v}")
    
    # 保存报告到文件
    report_file = f"test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n   详细报告已保存: {report_file}")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()
