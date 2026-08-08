"""
评估 Agent — AI 综合评估执行结果 + 质量评分 + 自动报告

工作流：
1. 加载执行结果 + 历史趋势
2. 规则化评分（通过率/稳定性/效率）
3. AI 深度评估（根因分析/风险评估/改进建议）
4. 综合评分 = 规则分*0.4 + AI分*0.6
5. 生成评估报告（TestReport + HTML）
"""
import json
import re
import time
import logging
from typing import List, Dict, Any, Optional, AsyncIterator

from .base_agent import BaseAgent
from core.tools.evaluation_storage import EvaluationStorageTool
from core.models.prompts.evaluation import (
    EVALUATION_SYSTEM,
    EVALUATION_USER,
    ROOT_CAUSE_SYSTEM,
    ROOT_CAUSE_USER,
    REPORT_SYSTEM,
    REPORT_USER,
)

logger = logging.getLogger(__name__)


class EvaluatorAgent(BaseAgent):
    """
    评估 Agent

    功能：
    1. 综合评估执行结果
    2. 规则引擎 + AI 双重评分
    3. 失败根因深度分析
    4. 风险等级判定
    5. 自动生成结构化 HTML 报告

    用法:
        agent = EvaluatorAgent(user_id=1)
        result = agent.run(
            prompt="评估执行结果",
            context={"execution_id": 42}
        )
    """

    name = "evaluator_agent"
    description = "智能评估测试执行结果，生成质量报告和改进建议"
    task_type = "generation"
    system_prompt = EVALUATION_SYSTEM

    def __init__(self, user_id: int = None, router=None):
        super().__init__(router=router)
        self.user_id = user_id
        self._storage = EvaluationStorageTool(user_id=user_id)

    # ============================================================
    # 同步入口
    # ============================================================

    def run(self, prompt: str, context: dict = None) -> dict:
        """
        同步执行评估

        Args:
            prompt: 评估描述
            context: {
                "execution_id": int,      # 必填：执行记录 ID
                "suite_id": int,          # 可选：关联套件（用于趋势分析）
                "trend_days": int,        # 趋势分析天数（默认7）
                "generate_html": bool,    # 是否生成 HTML 报告（默认 true）
            }

        Returns:
            {"status": "success|error", "data": {...}, "report_id": int, ...}
        """
        ctx = context or {}
        execution_id = ctx.get("execution_id")
        suite_id = ctx.get("suite_id")
        trend_days = ctx.get("trend_days", 7)
        generate_html = ctx.get("generate_html", True)

        if not execution_id:
            return self._error("缺少 execution_id 参数")

        try:
            # Step 1: 加载执行数据
            execution_data = self._load_execution(execution_id)
            if not execution_data:
                return self._error(f"执行记录 #{execution_id} 不存在或不可用")

            # Step 2: 加载历史趋势
            history = self._storage.get_history(
                suite_id=suite_id or execution_data.get("suite_id"),
                days=trend_days,
                limit=10,
            )

            # Step 3: 规则化评分
            stats = execution_data["stats"]
            rule_scores = self._storage.calculate_rule_score(
                passed=stats["passed"],
                failed=stats["failed"],
                skipped=stats["skipped"],
                total=stats["total"],
                duration=stats["duration"],
                history=history,
            )

            # Step 4: AI 深度评估（失败用例+趋势）
            ai_evaluation = {}
            if stats["total"] > 0:
                ai_evaluation = self._ai_evaluate(execution_data, history, trend_days)

            # Step 5: 综合评分
            ai_score = ai_evaluation.get("overall", {}).get("score", 0)
            composite = self._composite_score(rule_scores["total_rule_score"], ai_score)

            # Step 6: 生成报告
            report_html = ""
            report_id = 0
            if generate_html:
                try:
                    report_html = self._generate_html(composite, ai_evaluation, rule_scores)
                except Exception as e:
                    logger.warning(f"[EvaluatorAgent] HTML 报告生成失败: {e}")

                save_result = self._storage.save_report(
                    execution_id=execution_id,
                    title=f"评估报告 - {execution_data.get('name', '执行')}",
                    summary=composite.get("summary", ""),
                    report_html=report_html,
                )
                if save_result.success:
                    report_id = save_result.report_id

            return self._success(
                data={
                    "execution_id": execution_id,
                    "composite_score": composite,
                    "rule_scores": rule_scores,
                    "ai_evaluation": ai_evaluation,
                    "report_id": report_id,
                    "history_trend": {
                        "count": len(history),
                        "days": trend_days,
                        "recent_runs": history[:5],
                    },
                },
                report_id=report_id,
                composite_grade=composite.get("grade"),
                composite_score=composite.get("score"),
            )

        except Exception as e:
            logger.exception(f"[EvaluatorAgent] 评估失败: {e}")
            return self._error(str(e))

    # ============================================================
    # 异步流式入口
    # ============================================================

    async def generate(
        self,
        execution_id: int,
        suite_id: int = None,
        trend_days: int = 7,
        generate_html: bool = True,
        stream: bool = True,
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        异步流式评估

        Args:
            execution_id: 执行记录 ID
            suite_id: 关联套件
            trend_days: 趋势天数
            generate_html: 是否生成 HTML
            stream: 是否流式输出

        Yields:
            进度事件 + 最终结果
        """
        try:
            # Step 1: 加载数据
            yield {"type": "progress", "stage": "load", "message": "加载执行数据..."}

            execution_data = self._load_execution(execution_id)
            if not execution_data:
                yield {"type": "error", "message": f"执行记录 #{execution_id} 不存在"}
                return

            stats = execution_data["stats"]
            yield {
                "type": "progress", "stage": "load",
                "message": f"已加载: {stats['total']}用例, "
                f"{stats['passed']}P/{stats['failed']}F/{stats['skipped']}S, "
                f"耗时{stats['duration']}s",
                "stats": stats,
            }

            # Step 2: 历史趋势
            yield {"type": "progress", "stage": "trend", "message": "加载历史趋势..."}
            history = self._storage.get_history(
                suite_id=suite_id or execution_data.get("suite_id"),
                days=trend_days,
                limit=10,
            )
            yield {
                "type": "progress", "stage": "trend",
                "message": f"近{trend_days}天共 {len(history)} 次执行记录",
            }

            # Step 3: 规则评分
            yield {"type": "progress", "stage": "rule_score", "message": "计算规则化评分..."}
            rule_scores = self._storage.calculate_rule_score(
                passed=stats["passed"],
                failed=stats["failed"],
                skipped=stats["skipped"],
                total=stats["total"],
                duration=stats["duration"],
                history=history,
            )
            yield {
                "type": "progress", "stage": "rule_score",
                "message": f"通过率{rule_scores['pass_score']}/40 + "
                f"稳定性{rule_scores['stability_score']}/30 + "
                f"效率{rule_scores['efficiency_score']}/30 = "
                f"{rule_scores['total_rule_score']}/100",
                "rule_scores": rule_scores,
            }

            # Step 4: AI 深度评估
            ai_evaluation = {}
            if stats["total"] > 0:
                yield {
                    "type": "progress", "stage": "ai_evaluate",
                    "message": "AI 正在深度分析执行结果...",
                }
                ai_evaluation = self._ai_evaluate(execution_data, history, trend_days)
                yield {
                    "type": "progress", "stage": "ai_evaluate",
                    "message": ai_evaluation.get("overall", {}).get("summary", "评估完成"),
                    "ai_evaluation": ai_evaluation,
                }

            # Step 5: 综合评分
            yield {"type": "progress", "stage": "composite", "message": "计算综合评分..."}
            ai_score = ai_evaluation.get("overall", {}).get("score", 0)
            composite = self._composite_score(rule_scores["total_rule_score"], ai_score)
            yield {
                "type": "progress", "stage": "composite",
                "message": f"综合评分: {composite['score']}/100, 等级: {composite['grade']}",
                "composite": composite,
            }

            # Step 6: 生成报告
            report_html = ""
            report_id = 0
            if generate_html:
                yield {
                    "type": "progress", "stage": "report",
                    "message": "生成评估报告...",
                }
                try:
                    report_html = self._generate_html(composite, ai_evaluation, rule_scores)
                except Exception as e:
                    logger.warning(f"[EvaluatorAgent] HTML 报告生成失败: {e}")
                    report_html = f"<p>报告生成失败: {e}</p>"

                save_result = self._storage.save_report(
                    execution_id=execution_id,
                    title=f"评估报告 - {execution_data.get('name', '执行')}",
                    summary=composite.get("summary", ""),
                    report_html=report_html,
                )
                if save_result.success:
                    report_id = save_result.report_id

                yield {
                    "type": "progress", "stage": "report",
                    "message": f"报告 #{report_id} 已生成",
                }

            # Step 7: 完成
            yield {
                "type": "done",
                "execution_id": execution_id,
                "composite_score": composite,
                "rule_scores": rule_scores,
                "ai_evaluation": ai_evaluation,
                "report_id": report_id,
                "report_html": report_html[:500] + "..." if len(report_html) > 500 else report_html,
            }

        except Exception as e:
            logger.exception(f"[EvaluatorAgent] 评估失败: {e}")
            yield {"type": "error", "message": str(e)}

    # ============================================================
    # 核心方法
    # ============================================================

    def _load_execution(self, execution_id: int) -> Optional[Dict]:
        """加载执行记录数据"""
        from execution.models import TestExecution

        try:
            exec_obj = TestExecution.objects.select_related('test_suite').get(id=execution_id)

            results = exec_obj.execution_results or []
            return {
                "execution_id": execution_id,
                "name": exec_obj.name or f"执行#{execution_id}",
                "status": exec_obj.status,
                "environment": exec_obj.environment,
                "suite_id": exec_obj.test_suite_id,
                "stats": {
                    "total": exec_obj.total_count or len(results),
                    "passed": exec_obj.passed_count,
                    "failed": exec_obj.failed_count,
                    "skipped": exec_obj.skipped_count,
                    "duration": exec_obj.duration or 0,
                },
                "results": results,
                "started_at": exec_obj.started_at.isoformat() if exec_obj.started_at else "",
            }
        except TestExecution.DoesNotExist:
            return None
        except Exception as e:
            logger.error(f"[EvaluatorAgent] 加载执行数据失败: {e}")
            return None

    def _ai_evaluate(self, execution_data: Dict, history: List[Dict], trend_days: int) -> Dict:
        """
        AI 深度评估执行结果

        包含：通过率分析、根因归类、风险评估、改进建议
        """
        stats = execution_data["stats"]
        results = execution_data.get("results", [])
        total = stats["total"]

        # 构建失败详情
        failed_cases = [r for r in results if r.get("status") == "failed"]
        failed_lines = []
        for i, fc in enumerate(failed_cases[:15]):
            title = fc.get("title", fc.get("case_title", "未知"))
            error = fc.get("error", "")[:150]
            assertion = json.dumps(fc.get("assertion_errors", []), ensure_ascii=False)[:200]
            resp_code = fc.get("response_status_code", "N/A")
            endpoint = fc.get("api_endpoint", fc.get("url", ""))
            failed_lines.append(
                f"[{i+1}] {title}\n"
                f"    端点: {fc.get('method','GET')} {endpoint}\n"
                f"    错误: {error}\n"
                f"    断言: {assertion}\n"
                f"    响应码: {resp_code}"
            )

        # 构建通过用例采样
        passed_cases = [r for r in results if r.get("status") == "passed"]
        passed_sample_lines = []
        for pc in passed_cases[:5]:
            title = pc.get("title", pc.get("case_title", "未知"))
            endpoint = pc.get("api_endpoint", pc.get("url", ""))
            passed_sample_lines.append(
                f"- {title} ({pc.get('method','GET')} {endpoint})"
            )

        # 构建历史趋势
        trend_lines = []
        for h in history:
            t = h.get("total", 0)
            p = h.get("passed", 0)
            f = h.get("failed", 0)
            rate = f"{p/t*100:.1f}%" if t > 0 else "N/A"
            trend_lines.append(
                f"- {h.get('started_at','?')[:16]} | "
                f"{h.get('status','?')} | "
                f"{rate} ({p}/{t}) | "
                f"耗时{h.get('duration',0)}s"
            )

        user_prompt = EVALUATION_USER.format(
            total_count=total,
            passed_count=stats["passed"],
            failed_count=stats["failed"],
            skipped_count=stats["skipped"],
            duration=stats["duration"],
            environment=execution_data.get("environment", "unknown"),
            failed_details="\n\n".join(failed_lines) if failed_lines else "无失败用例",
            trend_days=trend_days,
            trend_data="\n".join(trend_lines) if trend_lines else "无历史数据",
            passed_sample="\n".join(passed_sample_lines) if passed_sample_lines else "无",
        )

        try:
            response = self.ask_llm(prompt=user_prompt)
            result = self._parse_json(response)

            if not result:
                return self._fallback_evaluation(stats, history)

            # 确保包含所有必要字段
            if "overall" not in result:
                result["overall"] = {"score": 0, "grade": "D", "summary": "解析失败"}
            return result

        except Exception as e:
            logger.warning(f"[EvaluatorAgent] AI 评估失败: {e}")
            return self._fallback_evaluation(stats, history)

    def _fallback_evaluation(self, stats: Dict, history: List[Dict]) -> Dict:
        """AI 不可用时的回退评估"""
        total = stats["total"]
        passed = stats["passed"]
        failed = stats["failed"]
        pass_rate = passed / total if total > 0 else 0
        grade = self._grade(pass_rate)

        if pass_rate == 1.0:
            health = "healthy"
            summary = "全部用例通过，系统运行正常"
        elif pass_rate >= 0.80:
            health = "warning"
            summary = f"通过率 {pass_rate*100:.1f}%，部分用例失败需关注"
        else:
            health = "critical"
            summary = f"通过率仅 {pass_rate*100:.1f}%，存在严重问题"

        return {
            "overall": {
                "score": round(pass_rate * 100),
                "grade": grade,
                "health_status": health,
                "summary": summary,
            },
            "pass_rate_analysis": {
                "rate": f"{pass_rate*100:.1f}%",
                "score": round(pass_rate * 25, 1),
                "evaluation": summary,
            },
            "root_cause_analysis": {
                "clusters": [],
                "primary_cause": "AI 不可用，无法分析",
                "score": 0,
            },
            "risk_assessment": {
                "level": health,
                "details": [f"{failed} 个用例失败"] if failed else [],
                "has_critical_failures": failed > 0,
                "score": max(0, round(25 - failed * 5)),
            },
            "recommendations": [
                {"priority": "P1", "category": "执行", "action": "重新执行失败用例"}
            ] if failed > 0 else [],
        }

    def _composite_score(self, rule_score: float, ai_score: float) -> Dict:
        """
        综合评分 = 规则分*0.4 + AI分*0.6

        Returns:
            {score, grade, summary, rule_contrib, ai_contrib}
        """
        composite = round(rule_score * 0.4 + ai_score * 0.6, 1)
        grade = self._grade(composite / 100)

        if composite >= 90:
            summary = "优秀，系统质量很高，建议持续保持"
        elif composite >= 75:
            summary = "良好，存在少量优化空间"
        elif composite >= 60:
            summary = "一般，需关注失败用例并改进"
        elif composite >= 40:
            summary = "较差，存在较多问题，建议全面排查"
        else:
            summary = "很差，需要立即修复关键问题"

        return {
            "score": composite,
            "grade": grade,
            "summary": summary,
            "rule_contrib": round(rule_score * 0.4, 1),
            "ai_contrib": round(ai_score * 0.6, 1),
        }

    def _generate_html(self, composite: Dict, ai_eval: Dict, rule_scores: Dict) -> str:
        """生成 HTML 评估报告"""
        overall = ai_eval.get("overall", {})
        root_cause = ai_eval.get("root_cause_analysis", {})
        risk = ai_eval.get("risk_assessment", {})
        recommendations = ai_eval.get("recommendations", [])
        pass_rate_analysis = ai_eval.get("pass_rate_analysis", {})

        # 等级颜色
        grade_colors = {"A": "#22c55e", "B": "#3b82f6", "C": "#f59e0b", "D": "#ef4444"}
        health_colors = {"healthy": "#22c55e", "warning": "#f59e0b", "critical": "#ef4444"}

        grade = composite.get("grade", "D")
        health = overall.get("health_status", "warning")

        # 根因聚类进度条
        clusters_html = ""
        clusters = root_cause.get("clusters", [])
        if clusters:
            for c in clusters:
                cat = c.get("category", "未知")
                ratio_str = c.get("ratio", "0%")
                try:
                    ratio_num = float(ratio_str.replace("%", ""))
                except (ValueError, AttributeError):
                    ratio_num = 0
                clusters_html += f"""
                <div style="margin:8px 0">
                    <div style="display:flex;justify-content:space-between;font-size:13px">
                        <span>{cat}</span><span>{c.get('count', 0)} 个 ({ratio_str})</span>
                    </div>
                    <div style="background:#e5e7eb;border-radius:4px;height:8px;margin-top:4px">
                        <div style="width:{ratio_num}%;background:#3b82f6;height:8px;border-radius:4px"></div>
                    </div>
                    <div style="font-size:12px;color:#6b7280;margin-top:2px">{c.get('description', '')}</div>
                </div>"""

        # 建议列表
        recs_html = ""
        for rec in recommendations:
            priority = rec.get("priority", "P2")
            p_colors = {"P0": "#ef4444", "P1": "#f59e0b", "P2": "#3b82f6"}
            recs_html += f"""
            <div style="display:flex;align-items:start;gap:10px;padding:10px;background:#f9fafb;
                        border-radius:6px;margin:6px 0">
                <span style="background:{p_colors.get(priority, '#9ca3af')};color:#fff;
                             padding:2px 8px;border-radius:4px;font-size:12px;font-weight:700;
                             white-space:nowrap">{priority}</span>
                <div>
                    <div style="font-size:13px;color:#374151">{rec.get('action', '')}</div>
                    <div style="font-size:11px;color:#9ca3af">{rec.get('category', '')}</div>
                </div>
            </div>"""

        return f"""
<div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
            max-width:800px;margin:0 auto;padding:20px;color:#1f2937">
    
    <!-- 概览卡片 -->
    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:24px">
        <div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;padding:16px;text-align:center">
            <div style="font-size:28px;font-weight:700;color:#16a34a">{composite.get('score', 0)}</div>
            <div style="font-size:12px;color:#6b7280;margin-top:4px">综合评分</div>
        </div>
        <div style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:8px;padding:16px;text-align:center">
            <div style="font-size:28px;font-weight:700;color:{grade_colors.get(grade, '#6b7280')}">{grade}</div>
            <div style="font-size:12px;color:#6b7280;margin-top:4px">质量等级</div>
        </div>
        <div style="background:#fefce8;border:1px solid #fef08a;border-radius:8px;padding:16px;text-align:center">
            <div style="font-size:28px;font-weight:700;color:#ca8a04">{pass_rate_analysis.get('rate', 'N/A')}</div>
            <div style="font-size:12px;color:#6b7280;margin-top:4px">通过率</div>
        </div>
        <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:16px;text-align:center">
            <div style="font-size:12px;padding:4px 12px;border-radius:12px;
                        background:{health_colors.get(health, '#9ca3af')};color:#fff;display:inline-block">
                {health.upper()}
            </div>
            <div style="font-size:12px;color:#6b7280;margin-top:4px">健康状态</div>
        </div>
    </div>

    <!-- 评分明细 -->
    <div style="background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:20px;margin-bottom:16px">
        <h3 style="margin:0 0 16px;font-size:16px">评分明细</h3>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
            <div>
                <div style="font-size:13px;font-weight:600;color:#6b7280;margin-bottom:8px">规则化评分</div>
                <div style="height:8px;background:#e5e7eb;border-radius:4px;margin-bottom:8px">
                    <div style="width:{rule_scores.get('total_rule_score',0)}%;height:8px;
                                background:#8b5cf6;border-radius:4px"></div>
                </div>
                <div style="font-size:12px;color:#6b7280">
                    通过率 {rule_scores.get('pass_score',0)} + 稳定性 {rule_scores.get('stability_score',0)} + 效率 {rule_scores.get('efficiency_score',0)} = {rule_scores.get('total_rule_score',0)}/100
                </div>
            </div>
            <div>
                <div style="font-size:13px;font-weight:600;color:#6b7280;margin-bottom:8px">AI 深度评估</div>
                <div style="height:8px;background:#e5e7eb;border-radius:4px;margin-bottom:8px">
                    <div style="width:{overall.get('score',0)}%;height:8px;
                                background:#06b6d4;border-radius:4px"></div>
                </div>
                <div style="font-size:12px;color:#6b7280">{overall.get('score',0)}/100 — {overall.get('summary','')}</div>
            </div>
        </div>
        <div style="margin-top:12px;font-size:12px;color:#9ca3af">
            综合评分 = 规则分×0.4 + AI分×0.6 = {composite.get('score',0)}
        </div>
    </div>

    <!-- 根因分析 -->
    <div style="background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:20px;margin-bottom:16px">
        <h3 style="margin:0 0 12px;font-size:16px">失败根因分析</h3>
        <div style="font-size:13px;color:#6b7280;margin-bottom:12px">
            主要根因: <strong style="color:#1f2937">{root_cause.get('primary_cause', 'N/A')}</strong>
        </div>
        {clusters_html if clusters_html else '<div style="font-size:13px;color:#9ca3af">无失败用例或未进行根因分析</div>'}
    </div>

    <!-- 风险评估 -->
    <div style="background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:20px;margin-bottom:16px">
        <h3 style="margin:0 0 12px;font-size:16px">风险评估</h3>
        <div style="font-size:13px;margin-bottom:8px">
            风险等级: 
            <span style="font-weight:700;color:{health_colors.get(risk.get('level','medium'), '#9ca3af')}">
                {risk.get('level', 'unknown').upper()}
            </span>
            {' | ⚠️ 存在关键失败' if risk.get('has_critical_failures') else ' | ✅ 无关键失败'}
        </div>
        <ul style="font-size:13px;color:#374151;margin:0;padding-left:20px">
            {''.join(f'<li style="margin:4px 0">{d}</li>' for d in risk.get('details', []))}
        </ul>
    </div>

    <!-- 改进建议 -->
    <div style="background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:20px;margin-bottom:16px">
        <h3 style="margin:0 0 12px;font-size:16px">改进建议</h3>
        {recs_html if recs_html else '<div style="font-size:13px;color:#9ca3af">无建议</div>'}
    </div>

    <!-- 评估摘要 -->
    <div style="background:#fefce8;border:1px solid #fde68a;border-radius:8px;padding:16px">
        <div style="font-size:13px;font-weight:600;color:#92400e;margin-bottom:4px">评估摘要</div>
        <div style="font-size:14px;color:#78350f">{composite.get('summary', '')}</div>
    </div>

</div>"""

    # ============================================================
    # 工具方法
    # ============================================================

    @staticmethod
    def _grade(pass_rate: float) -> str:
        """通过率→等级"""
        if pass_rate >= 0.90:
            return "A"
        elif pass_rate >= 0.75:
            return "B"
        elif pass_rate >= 0.60:
            return "C"
        return "D"

    @staticmethod
    def _parse_json(text: str) -> dict:
        """容错 JSON 解析"""
        code_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
        if code_match:
            text = code_match.group(1)

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        brace_match = re.search(r'\{[\s\S]*\}', text)
        if brace_match:
            try:
                return json.loads(brace_match.group(0))
            except json.JSONDecodeError:
                pass

        logger.warning(f"[EvaluatorAgent] JSON 解析失败: {text[:200]}")
        return {}

    def get_tools(self) -> List[dict]:
        return [
            self._storage.to_openai_function(),
        ]


# 工厂函数
def create_evaluator(user_id: int = None) -> EvaluatorAgent:
    return EvaluatorAgent(user_id=user_id)
