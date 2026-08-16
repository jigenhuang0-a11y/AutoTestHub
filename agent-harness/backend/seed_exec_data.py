"""
脚本：生成一条真实测试执行记录及明细，用于填充测试报告页。
"""
import sys, os, json
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv()

from app.core.task_store import get_task_store

now = datetime.now(timezone.utc).isoformat()
exec_id = "exec-report-demo"

results = [
    {
        "case_id": "tc-001",
        "case_title": "登录接口 - 正常登录",
        "status": "passed",
        "duration_ms": 45,
        "response_body": json.dumps({"code": 0, "token": "eyJhbGciOiJIUzI1NiIs"}, ensure_ascii=False),
        "assertions": json.dumps([{"name": "状态码 200", "passed": True}, {"name": "返回 token", "passed": True}], ensure_ascii=False),
        "extracted_vars": json.dumps({"token": "eyJhbGciOiJIUzI1NiIs"}, ensure_ascii=False),
        "error_message": "",
    },
    {
        "case_id": "tc-002",
        "case_title": "登录接口 - 密码错误",
        "status": "passed",
        "duration_ms": 38,
        "response_body": json.dumps({"code": 10001, "msg": "用户名或密码错误"}, ensure_ascii=False),
        "assertions": json.dumps([{"name": "状态码 401", "passed": True}, {"name": "错误提示明确", "passed": True}], ensure_ascii=False),
        "extracted_vars": json.dumps({}, ensure_ascii=False),
        "error_message": "",
    },
    {
        "case_id": "tc-003",
        "case_title": "商品列表 - 分页查询",
        "status": "passed",
        "duration_ms": 62,
        "response_body": json.dumps({"total": 100, "list": [{"id": 1, "name": "iPhone 16"}]}, ensure_ascii=False),
        "assertions": json.dumps([{"name": "返回 list 数组", "passed": True}, {"name": "total > 0", "passed": True}], ensure_ascii=False),
        "extracted_vars": json.dumps({"first_id": 1}, ensure_ascii=False),
        "error_message": "",
    },
    {
        "case_id": "tc-004",
        "case_title": "购物车 - 加入商品",
        "status": "failed",
        "duration_ms": 120,
        "response_body": json.dumps({"code": 0, "cart_id": None}, ensure_ascii=False),
        "assertions": json.dumps([{"name": "返回 cart_id", "passed": False}], ensure_ascii=False),
        "extracted_vars": json.dumps({}, ensure_ascii=False),
        "error_message": "断言失败：期望 cart_id 为整数，实际为 null",
    },
    {
        "case_id": "tc-005",
        "case_title": "下单接口 - 库存不足",
        "status": "skipped",
        "duration_ms": 0,
        "response_body": "",
        "assertions": json.dumps([], ensure_ascii=False),
        "extracted_vars": json.dumps({}, ensure_ascii=False),
        "error_message": "前置步骤失败，跳过",
    },
]

store = get_task_store()
store.create_execution({
    "exec_id": exec_id,
    "name": "全链路冒烟测试报告",
    "status": "completed",
    "total_cases": 5,
    "passed_cases": 3,
    "failed_cases": 1,
    "skipped_cases": 1,
    "duration": 2.65,
    "trigger_type": "manual",
    "summary": "核心登录/商品/购物车链路验证，购物车 cart_id 返回异常需修复。",
    "results": results,
})
print(f"[OK] 测试执行记录已创建: {exec_id}")
