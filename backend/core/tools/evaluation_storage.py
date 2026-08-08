"""
评估存储工具 — 封装 TestReport 模型 + 规则化评分计算
"""
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

from django.utils import timezone

logger = logging.getLogger(__name__)


@dataclass
class EvaluationStorageResult:
    """评估存储结果"""
    success: bool
    report_id: int = 0
    error: str = ""


class EvaluationStorageTool:
    """
    评估存储工具

    职责：
    1. 创建/更新 TestReport 报告
    2. 计算规则化评分（通过率/稳定性/效率）
    3. 拉取历史执行记录用于趋势分析
    """

    name = "evaluation_storage"
    description = "存储评估报告、计算规则评分、拉取历史趋势"

    def __init__(self, user_id: int = None):
        self.user_id = user_id

    # ============================================================
    # 报告存储
    # ============================================================

    def save_report(
        self,
        execution_id: int,
        title: str = "",
        summary: str = "",
        report_html: str = "",
        report_path: str = "",
    ) -> EvaluationStorageResult:
        """
        创建或更新测试报告（与 TestExecution 一对一）

        Args:
            execution_id: 执行记录 ID
            title: 报告标题
            summary: 摘要
            report_html: HTML 报告内容
            report_path: 报告文件路径
        """
        from reports.models import TestReport
        from execution.models import TestExecution

        try:
            execution = TestExecution.objects.get(id=execution_id)

            # 检查是否存在已有报告
            report, created = TestReport.objects.update_or_create(
                execution=execution,
                defaults={
                    'title': title or f'测试报告 - {execution.name or execution_id}',
                    'summary': summary,
                    'report_html': report_html,
                    'report_path': report_path,
                },
            )

            logger.info(
                f"[EvaluationStorage] {'创建' if created else '更新'}报告 "
                f"#{report.id}, execution=#{execution_id}"
            )
            return EvaluationStorageResult(success=True, report_id=report.id)

        except TestExecution.DoesNotExist:
            logger.error(f"[EvaluationStorage] 执行记录不存在: #{execution_id}")
            return EvaluationStorageResult(success=False, error=f"执行记录不存在: #{execution_id}")
        except Exception as e:
            logger.error(f"[EvaluationStorage] 保存报告失败: {e}")
            return EvaluationStorageResult(success=False, error=str(e))

    # ============================================================
    # 规则化评分
    # ============================================================

    def calculate_rule_score(
        self,
        passed: int,
        failed: int,
        skipped: int,
        total: int,
        duration: int,
        history: List[Dict] = None,
    ) -> Dict[str, Any]:
        """
        基于规则引擎计算初步评分

        维度：
        1. 通过率评分 (40分) — pass_rate * 40
        2. 稳定性评分 (30分) — 与历史相比的波动程度
        3. 效率评分 (30分) — 执行耗时评估

        Returns:
            {pass_score, stability_score, efficiency_score, total_rule_score, details}
        """
        if total == 0:
            return {
                'pass_score': 0,
                'stability_score': 0,
                'efficiency_score': 0,
                'total_rule_score': 0,
                'details': '无可用数据',
            }

        # 1. 通过率评分 (0-40)
        pass_rate = passed / total
        pass_score = round(pass_rate * 40, 1)

        # 2. 稳定性评分 (0-30)
        stability_score = 30.0  # 默认满分
        details_parts = [f"通过率: {pass_rate*100:.1f}%"]

        if history and len(history) >= 2:
            hist_rates = []
            for h in history[:10]:  # 最近10次
                t = h.get('total', 0)
                p = h.get('passed', 0)
                if t > 0:
                    hist_rates.append(p / t)

            if len(hist_rates) >= 2:
                avg_rate = sum(hist_rates) / len(hist_rates)
                variance = sum((r - avg_rate) ** 2 for r in hist_rates) / len(hist_rates)
                std_dev = variance ** 0.5

                # 标准差 < 0.05 稳定性满分，0.05-0.15 略有波动，>0.15 不稳定
                if std_dev < 0.05:
                    stability_score = 30.0
                    stability_label = "非常稳定"
                elif std_dev < 0.10:
                    stability_score = 24.0
                    stability_label = "稳定"
                elif std_dev < 0.15:
                    stability_score = 18.0
                    stability_label = "略有波动"
                elif std_dev < 0.25:
                    stability_score = 10.0
                    stability_label = "波动较大"
                else:
                    stability_score = 4.0
                    stability_label = "不稳定"

                details_parts.append(
                    f"历史平均通过率: {avg_rate*100:.1f}%, "
                    f"标准差: {std_dev*100:.1f}%, "
                    f"稳定性: {stability_label}"
                )

                # 与历史均值对比扣分
                if pass_rate < avg_rate - 0.1:
                    stability_score = max(0, stability_score - 8)
                    details_parts.append("当前通过率显著低于历史均值")
        else:
            details_parts.append("历史数据不足，稳定性评分为默认值")

        stability_score = round(min(30, max(0, stability_score)), 1)

        # 3. 效率评分 (0-30)
        efficiency_score = 30.0
        avg_time_per_case = duration / total if total > 0 else 0

        if avg_time_per_case > 30:
            efficiency_score = 5.0
            details_parts.append(f"平均每用例耗时 {avg_time_per_case:.1f}s，效率极低")
        elif avg_time_per_case > 15:
            efficiency_score = 12.0
            details_parts.append(f"平均每用例耗时 {avg_time_per_case:.1f}s，效率较低")
        elif avg_time_per_case > 5:
            efficiency_score = 20.0
            details_parts.append(f"平均每用例耗时 {avg_time_per_case:.1f}s，效率一般")
        elif avg_time_per_case > 1:
            efficiency_score = 26.0
            details_parts.append(f"平均每用例耗时 {avg_time_per_case:.1f}s，效率良好")
        else:
            details_parts.append(f"平均每用例耗时 {avg_time_per_case:.1f}s，效率优秀")

        efficiency_score = round(efficiency_score, 1)
        total_rule_score = round(pass_score + stability_score + efficiency_score, 1)

        return {
            'pass_score': pass_score,
            'stability_score': stability_score,
            'efficiency_score': efficiency_score,
            'total_rule_score': total_rule_score,
            'details': '; '.join(details_parts),
        }

    # ============================================================
    # 历史趋势
    # ============================================================

    def get_history(self, suite_id: int = None, days: int = 7, limit: int = 10) -> List[Dict]:
        """拉取历史执行记录用于趋势分析"""
        from execution.models import TestExecution

        since = timezone.now() - timezone.timedelta(days=days)

        qs = TestExecution.objects.filter(
            started_at__gte=since,
            status__in=['completed', 'partial', 'failed'],
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
        if action == "evaluate_run":
            # 1. 拉取执行记录
            from execution.models import TestExecution
            execution_id = kwargs.get("execution_id")
            try:
                execution = TestExecution.objects.get(id=execution_id)
            except TestExecution.DoesNotExist:
                return {"error": f"Execution #{execution_id} not found"}

            # 2. 规则化评分
            score = self.calculate_rule_score(
                passed=execution.passed_count,
                failed=execution.failed_count,
                skipped=execution.skipped_count,
                total=execution.total_count,
                duration=execution.duration or 0,
                history=self.get_history(
                    suite_id=execution.test_suite_id,
                    days=kwargs.get("days", 7),
                    limit=kwargs.get("limit", 10),
                ),
            )

            # 3. 保存评估报告
            title = f"评估报告 - {execution.name or execution_id}"
            summary = f"规则评分: {score['total_rule_score']}/100; {score['details']}"
            result = self.save_report(
                execution_id=execution_id,
                title=title,
                summary=summary,
                report_html=kwargs.get("report_html", ""),
                report_path=kwargs.get("report_path", ""),
            )

            return {
                "success": result.success,
                "report_id": result.report_id,
                "score": score,
                "execution": {
                    "id": execution.id,
                    "status": execution.status,
                    "passed": execution.passed_count,
                    "failed": execution.failed_count,
                    "total": execution.total_count,
                },
            }
        if action == "save_report":
            result = self.save_report(**kwargs)
            return {"success": result.success, "report_id": result.report_id, "error": result.error}
        if action == "get_history":
            return {"history": self.get_history(**kwargs)}
        if action == "calculate_rule_score":
            return self.calculate_rule_score(**kwargs)
        logger.warning(f"[EvaluationStorageTool] 未知 action: {action}")
        return {"error": f"unknown action: {action}"}

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
                            "enum": ["save_report", "get_history"],
                        },
                        "execution_id": {"type": "integer"},
                        "suite_id": {"type": "integer"},
                        "title": {"type": "string"},
                        "summary": {"type": "string"},
                        "report_html": {"type": "string"},
                    },
                    "required": ["action"],
                },
            },
        }
