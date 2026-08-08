"""
用例存储工具 — Agent 生成用例后保存到数据库
"""
import json
import logging
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class TestCaseInput(BaseModel):
    """Agent 生成的用例结构"""
    title: str = Field(description="用例标题")
    description: str = Field(default="", description="用例描述")
    api_endpoint: str = Field(default="", description="接口地址")
    method: str = Field(default="GET", description="请求方法")
    headers: Dict[str, str] = Field(default_factory=dict, description="请求头")
    request_body: Dict[str, Any] = Field(default_factory=dict, description="请求体")
    expected_response: Dict[str, Any] = Field(default_factory=dict, description="预期响应")
    assertion_rules: List[Dict] = Field(default_factory=list, description="断言规则")
    extract_rules: List[Dict] = Field(default_factory=list, description="提取规则")
    priority: str = Field(default="P2", description="优先级 P0/P1/P2/P3")
    tags: List[str] = Field(default_factory=list, description="标签")
    assertions: str = Field(default="", description="断言说明文本")


class SaveResult(BaseModel):
    """保存结果"""
    success: bool
    case_id: Optional[int] = None
    title: str = ""
    error: str = ""


class TestCaseStorageTool:
    """
    用例存储工具
    Agent 生成用例后，通过此工具将用例保存到 TestCase 表中
    """

    name = "save_testcases"
    description = "将生成的测试用例批量保存到数据库"

    def __init__(self, user_id: int = None):
        self.user_id = user_id

    def save_cases(
        self,
        cases: List[dict],
        batch_name: str = "",
    ) -> List[SaveResult]:
        """
        批量保存用例

        Args:
            cases: 用例列表，每个元素符合 TestCaseInput 结构
            batch_name: 批次名称（用于打标签）

        Returns:
            保存结果列表
        """
        results = []
        for i, case_data in enumerate(cases):
            try:
                # 验证数据
                case_input = TestCaseInput(**case_data)

                # 创建用例
                from testcases.models import TestCase
                tc = TestCase(
                    title=case_input.title,
                    description=case_input.description,
                    api_endpoint=case_input.api_endpoint,
                    method=case_input.method,
                    headers=case_input.headers or {},
                    request_body=case_input.request_body or {},
                    expected_response=case_input.expected_response or {},
                    assertion_rules=case_input.assertion_rules or [],
                    extract_rules=case_input.extract_rules or [],
                    priority=case_input.priority,
                    tags=case_input.tags + ([batch_name] if batch_name else []),
                    assertions=case_input.assertions,
                    status='draft',
                    created_by_id=self.user_id,
                )
                tc.save()
                results.append(SaveResult(
                    success=True,
                    case_id=tc.id,
                    title=tc.title,
                ))
                logger.info(f"[StorageTool] 用例已保存: #{tc.id} {tc.title}")

            except Exception as e:
                logger.error(f"[StorageTool] 用例保存失败 [{i}]: {e}")
                results.append(SaveResult(
                    success=False,
                    title=case_data.get("title", f"用例#{i}"),
                    error=str(e),
                ))

        return results

    def clear_batch(self, batch_name: str) -> int:
        """清除指定批次的所有用例"""
        from testcases.models import TestCase
        # 查找包含该 batch_name 标签的用例
        count = 0
        for tc in TestCase.objects.filter(status='draft'):
            if batch_name in (tc.tags or []):
                tc.delete()
                count += 1
        return count

    def execute(self, action: str = None, **kwargs):
        """
        MCP 统一入口

        Args:
            action: 工具动作名（testcase_search / testcase_create / testcase_batch_save）
            **kwargs: 工具参数
        """
        logger.info(f"[TestCaseStorageTool.execute] action={action}, kwargs={list(kwargs.keys())}")
        if action == "testcase_search":
            return self.search_cases(**kwargs)
        if action in ("testcase_create", "testcase_batch_save"):
            cases = kwargs.get("cases") or [kwargs]
            if not isinstance(cases, list):
                cases = [cases]
            results = self.save_cases(cases=cases, batch_name=kwargs.get("batch_name", ""))
            return {
                "success": all(r.success for r in results),
                "saved_count": sum(1 for r in results if r.success),
                "failed_count": sum(1 for r in results if not r.success),
                "results": [r.model_dump() for r in results],
            }
        logger.warning(f"[TestCaseStorageTool] 未知 action: {action}")
        return {"error": f"unknown action: {action}"}

    def search_cases(self, query: str = "", status: str = "all", priority: str = "all", limit: int = 20, offset: int = 0, **extra):
        """
        搜索测试用例

        Args:
            query: 关键词
            status: 状态筛选
            priority: 优先级筛选
            limit: 返回数量
            offset: 分页偏移
        """
        from testcases.models import TestCase
        qs = TestCase.objects.all()
        if status and status != "all":
            qs = qs.filter(status=status)
        if priority and priority != "all":
            qs = qs.filter(priority=priority)
        if query:
            qs = qs.filter(title__icontains=query)
        total = qs.count()
        cases = qs.order_by("-id")[offset:offset + limit]
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "cases": [
                {
                    "id": c.id,
                    "title": c.title,
                    "status": c.status,
                    "priority": c.priority,
                    "tags": c.tags,
                }
                for c in cases
            ],
        }

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "cases": {
                            "type": "array",
                            "description": "要保存的测试用例数组",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "title": {"type": "string", "description": "用例标题"},
                                    "description": {"type": "string", "description": "用例描述"},
                                    "api_endpoint": {"type": "string", "description": "接口地址"},
                                    "method": {"type": "string", "description": "HTTP方法", "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"]},
                                    "headers": {"type": "object", "description": "请求头"},
                                    "request_body": {"type": "object", "description": "请求体"},
                                    "expected_response": {"type": "object", "description": "预期响应"},
                                    "assertion_rules": {"type": "array", "description": "断言规则"},
                                    "priority": {"type": "string", "description": "优先级", "enum": ["P0", "P1", "P2", "P3"]},
                                    "tags": {"type": "array", "items": {"type": "string"}, "description": "标签"},
                                    "assertions": {"type": "string", "description": "断言说明"},
                                },
                                "required": ["title", "method", "api_endpoint"],
                            },
                        },
                    },
                    "required": ["cases"],
                },
            },
        }
