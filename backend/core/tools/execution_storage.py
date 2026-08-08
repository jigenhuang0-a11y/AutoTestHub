"""
执行结果存储工具 — Agent 封装 TestExecution 模型的读写操作
"""
import json
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from django.utils import timezone

logger = logging.getLogger(__name__)


@dataclass
class ExecutionCreateResult:
    """创建执行记录的结果"""
    success: bool
    execution_id: int = 0
    error: str = ""
    total_cases: int = 0


class ExecutionStorageTool:
    """
    执行结果存储工具

    职责：
    1. 创建 TestExecution 记录
    2. 更新执行状态和结果
    3. 拉取历史执行记录（用于趋势分析）
    """

    name = "execution_storage"
    description = "存储测试执行记录和结果"

    def __init__(self, user_id: int = None):
        self.user_id = user_id

    def create_execution(
        self,
        name: str = "",
        test_case_ids: List[int] = None,
        suite_id: int = None,
        trigger_type: str = "manual_suite",
        environment: str = "dev",
        global_variables: Dict = None,
    ) -> ExecutionCreateResult:
        """
        创建一条执行记录

        Args:
            name: 执行名称
            test_case_ids: 用例 ID 列表
            suite_id: 关联套件 ID
            trigger_type: 触发方式
            environment: 环境
            global_variables: 全局变量
        """
        from execution.models import TestExecution

        test_case_ids = test_case_ids or []

        try:
            execution = TestExecution.objects.create(
                name=name or f"Agent执行-{timezone.now().strftime('%Y%m%d%H%M%S')}",
                test_suite_id=suite_id,
                test_cases=[int(tcid) for tcid in test_case_ids],
                status='pending',
                trigger_type=trigger_type,
                environment=environment,
                total_count=len(test_case_ids),
                started_by_id=self.user_id,
            )

            logger.info(
                f"[ExecutionStorage] 创建执行记录 #{execution.id}, "
                f"{len(test_case_ids)} 个用例"
            )
            return ExecutionCreateResult(
                success=True,
                execution_id=execution.id,
                total_cases=len(test_case_ids),
            )

        except Exception as e:
            logger.error(f"[ExecutionStorage] 创建执行记录失败: {e}")
            return ExecutionCreateResult(success=False, error=str(e))

    def update_status(
        self,
        execution_id: int,
        status: str,
        results: List[Dict] = None,
        passed: int = 0,
        failed: int = 0,
        skipped: int = 0,
        duration: int = 0,
        allure_report_path: str = "",
    ) -> bool:
        """
        更新执行记录状态

        Args:
            execution_id: 执行记录 ID
            status: 状态 (completed/failed/partial)
            results: 详细执行结果列表
            passed: 通过数
            failed: 失败数
            skipped: 跳过数
            duration: 耗时(秒)
            allure_report_path: Allure 报告路径
        """
        from execution.models import TestExecution

        try:
            execution = TestExecution.objects.get(id=execution_id)
            execution.status = status
            execution.execution_results = results or []
            execution.passed_count = passed
            execution.failed_count = failed
            execution.skipped_count = skipped
            execution.duration = duration
            if allure_report_path:
                execution.allure_report_path = allure_report_path
            if status in ('completed', 'failed', 'partial'):
                execution.completed_at = timezone.now()
            execution.save()

            logger.info(
                f"[ExecutionStorage] 更新执行记录 #{execution_id}: "
                f"status={status}, p={passed}, f={failed}, s={skipped}"
            )
            return True

        except TestExecution.DoesNotExist:
            logger.error(f"[ExecutionStorage] 执行记录不存在: #{execution_id}")
            return False
        except Exception as e:
            logger.error(f"[ExecutionStorage] 更新失败: {e}")
            return False

    def update_log(self, execution_id: int, log_line: str) -> bool:
        """追加执行日志"""
        from execution.models import TestExecution

        try:
            execution = TestExecution.objects.get(id=execution_id)
            execution.execution_log = (execution.execution_log or "") + "\n" + log_line
            execution.save(update_fields=['execution_log'])
            return True
        except Exception:
            return False

    def get_failed_cases(self, execution_id: int) -> List[Dict]:
        """获取失败用例的详细信息"""
        from execution.models import TestExecution

        try:
            execution = TestExecution.objects.get(id=execution_id)
            results = execution.execution_results or []
            return [r for r in results if r.get('status') == 'failed']
        except Exception:
            return []

    def get_history(
        self,
        suite_id: int = None,
        days: int = 7,
        limit: int = 20,
    ) -> List[Dict]:
        """
        拉取历史执行记录，用于趋势分析

        Args:
            suite_id: 按套件过滤
            days: 最近 N 天
            limit: 最大返回数
        """
        from execution.models import TestExecution
        from django.utils import timezone

        since = timezone.now() - timezone.timedelta(days=days)

        qs = TestExecution.objects.filter(
            started_at__gte=since,
        ).order_by('-started_at')

        if suite_id:
            qs = qs.filter(test_suite_id=suite_id)

        executions = qs[:limit]

        return [
            {
                "id": e.id,
                "name": e.name,
                "status": e.status,
                "total": e.total_count,
                "passed": e.passed_count,
                "failed": e.failed_count,
                "skipped": e.skipped_count,
                "duration": e.duration,
                "started_at": e.started_at.isoformat() if e.started_at else "",
            }
            for e in executions
        ]

    def execute(self, action: str = None, **kwargs) -> dict:
        """MCP 统一入口"""
        logger.info(f"[ExecutionStorageTool.execute] action={action}, kwargs={list(kwargs.keys())}")
        if action == "execution_status":
            from execution.models import TestExecution
            execution_id = kwargs.get("execution_id")
            try:
                execution = TestExecution.objects.get(id=execution_id)
                return {
                    "execution_id": execution.id,
                    "status": execution.status,
                    "total": execution.total_count,
                    "passed": execution.passed_count,
                    "failed": execution.failed_count,
                    "skipped": execution.skipped_count,
                    "duration": execution.duration,
                    "started_at": execution.started_at.isoformat() if execution.started_at else "",
                    "completed_at": execution.completed_at.isoformat() if execution.completed_at else "",
                }
            except TestExecution.DoesNotExist:
                return {"error": f"Execution #{execution_id} not found"}
        if action == "create":
            result = self.create_execution(**kwargs)
            return result.model_dump() if hasattr(result, "model_dump") else {"success": result.success, "execution_id": result.execution_id, "total_cases": result.total_cases, "error": result.error}
        if action == "update":
            ok = self.update_status(**kwargs)
            return {"success": ok}
        if action == "get_failed":
            return {"failed_cases": self.get_failed_cases(kwargs.get("execution_id"))}
        if action == "get_history":
            return {"history": self.get_history(**kwargs)}
        logger.warning(f"[ExecutionStorageTool] 未知 action: {action}")
        return {"error": f"unknown action: {action}"}

        """转为 OpenAI Function Calling 格式"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["create", "update", "get_failed", "get_history"],
                        },
                        "execution_id": {"type": "integer"},
                        "test_case_ids": {"type": "array", "items": {"type": "integer"}},
                        "suite_id": {"type": "integer"},
                        "status": {"type": "string"},
                    },
                    "required": ["action"],
                },
            },
        }
