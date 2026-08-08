"""
执行引擎 Agent — 智能执行测试 + 失败重试 + AI 诊断 + Allure 报告

功能：
1. 智能执行测试套件/用例
2. 失败自动重试（可配置次数 + 智能策略）
3. AI 分析失败原因并给出修改建议
4. 生成 Allure HTML 报告 + JSON 摘要
5. 流式进度输出
"""
import json
import re
import time
import logging
from typing import List, Dict, Any, Optional, AsyncIterator

from django.utils import timezone

from .base_agent import BaseAgent
from core.tools.execution_storage import ExecutionStorageTool
from core.tools.allure_reporter import AllureReporterTool
from core.models.prompts.execution import (
    FAILURE_ANALYSIS_SYSTEM,
    FAILURE_ANALYSIS_USER,
    EXECUTION_SUMMARY_SYSTEM,
    EXECUTION_SUMMARY_USER,
    RETRY_STRATEGY_SYSTEM,
)

logger = logging.getLogger(__name__)


class ExecutionEngineAgent(BaseAgent):
    """
    执行引擎 Agent

    工作流：
    1. 接收执行请求 → 创建 TestExecution 记录
    2. 调用 TestExecutionEngine.execute() 执行测试
    3. 解析结果 → 判断是否需要重试
    4. 如果失败：AI 分析失败原因 → 智能重试（最多 N 次）
    5. 生成 Allure 报告 + 执行总结
    6. 返回完整结果

    用法:
        agent = ExecutionEngineAgent(user_id=1)
        async for event in agent.generate(
            suite_id=1,
            environment="test",
            max_retries=2,
        ):
            print(event)
    """

    name = "execution_agent"
    description = "智能执行测试套件，支持失败重试和 Allure 报告"
    task_type = "generation"
    system_prompt = FAILURE_ANALYSIS_SYSTEM

    def __init__(self, user_id: int = None, router=None):
        super().__init__(router=router)
        self.user_id = user_id
        self._storage = ExecutionStorageTool(user_id=user_id)
        self._allure = AllureReporterTool()

    def run(self, prompt: str, context: dict = None) -> dict:
        """
        同步执行接口（兼容 BaseAgent）

        Args:
            prompt: 执行描述
            context: {
                "suite_id": int,          # 套件 ID
                "test_case_ids": [int],   # 或直接指定用例列表
                "environment": "dev/test/prod",
                "max_retries": int,       # 最大重试次数
                "global_variables": dict, # 全局变量
                "analyze_failures": bool, # 是否 AI 分析失败
            }

        Returns:
            {"status": "success|error", "execution_id": int, "stats": {...}, "report": {...}}
        """
        ctx = context or {}
        suite_id = ctx.get("suite_id")
        test_case_ids = ctx.get("test_case_ids", [])
        environment = ctx.get("environment", "dev")
        max_retries = ctx.get("max_retries", 2)
        global_variables = ctx.get("global_variables", {})
        analyze_failures = ctx.get("analyze_failures", True)

        try:
            # Step 1: 创建执行记录
            result = self._storage.create_execution(
                name=f"Agent执行-{suite_id or len(test_case_ids)}个用例",
                test_case_ids=test_case_ids,
                suite_id=suite_id,
                environment=environment,
                global_variables=global_variables,
            )

            if not result.success:
                return self._error(f"创建执行记录失败: {result.error}")

            execution_id = result.execution_id

            # Step 2: 执行
            exec_result = self._execute_suite(execution_id, global_variables)

            if not exec_result.get("success"):
                return self._error(f"执行失败: {exec_result.get('error', '未知错误')}")

            # Step 3: 重试（如果失败）
            retry_count = 0
            while exec_result.get("failed", 0) > 0 and retry_count < max_retries:
                retry_count += 1

                # AI 分析失败原因
                failure_analysis = {}
                if analyze_failures:
                    failed_cases = self._storage.get_failed_cases(execution_id)
                    if failed_cases:
                        failure_analysis = self._analyze(failed_cases)

                # 判断是否值得重试
                if failure_analysis.get("retry_worthy_cases"):
                    logger.info(
                        f"[ExecutionAgent] 重试 {retry_count}/{max_retries}: "
                        f"{len(failure_analysis['retry_worthy_cases'])} 个用例"
                    )
                    # 只重试值得重试的失败用例
                    retry_case_ids = [c["case_id"] for c in failure_analysis["retry_worthy_cases"]]

                    self._storage.update_log(
                        execution_id,
                        f"[Agent] 第{retry_count}次重试，{len(retry_case_ids)}个用例"
                    )

                    # 创建新的执行记录做重试
                    retry_result = self._storage.create_execution(
                        name=f"重试-{retry_count}-exec_{execution_id}",
                        test_case_ids=retry_case_ids,
                        suite_id=suite_id,
                        environment=environment,
                    )
                    if retry_result.success:
                        retry_exec = self._execute_suite(
                            retry_result.execution_id,
                            global_variables,
                        )
                        # 合并重试结果
                        exec_result = self._merge_results(exec_result, retry_exec, execution_id)

                else:
                    logger.info("[ExecutionAgent] AI 分析认为无需重试，跳过")
                    break

            # Step 4: 更新最终状态
            final_stats = {
                "total": exec_result.get("total", 0),
                "passed": exec_result.get("passed", 0),
                "failed": exec_result.get("failed", 0),
                "skipped": exec_result.get("skipped", 0),
                "duration": exec_result.get("duration", 0),
                "retries": retry_count,
            }

            final_status = "completed" if final_stats["failed"] == 0 else (
                "partial" if final_stats["passed"] > 0 else "failed"
            )

            self._storage.update_status(
                execution_id=execution_id,
                status=final_status,
                results=exec_result.get("results", []),
                passed=final_stats["passed"],
                failed=final_stats["failed"],
                skipped=final_stats["skipped"],
                duration=final_stats["duration"],
            )

            # Step 5: AI 执行总结
            execution_summary = {}
            if analyze_failures and final_stats["total"] > 0:
                try:
                    execution_summary = self._summarize(exec_result)
                except Exception as e:
                    logger.warning(f"[ExecutionAgent] 总结生成失败: {e}")

            # Step 6: Allure 报告
            report = self._allure.build_report_bundle(
                execution_id=execution_id,
                execution_results=exec_result.get("results", []),
                execution_stats=final_stats,
            )

            return self._success(
                data={
                    "execution_id": execution_id,
                    "stats": final_stats,
                    "summary": execution_summary,
                    "report": report,
                    "results": exec_result.get("results", [])[:20],  # 前20条预览
                },
                **final_stats,
            )

        except Exception as e:
            logger.exception(f"[ExecutionAgent] 执行失败: {e}")
            return self._error(str(e))

    async def generate(
        self,
        suite_id: int = None,
        test_case_ids: List[int] = None,
        environment: str = "dev",
        max_retries: int = 2,
        global_variables: Dict = None,
        analyze_failures: bool = True,
        stream: bool = True,
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        异步主入口：流式执行测试

        Args:
            suite_id: 套件 ID
            test_case_ids: 用例 ID 列表
            environment: 执行环境
            max_retries: 最大重试次数
            global_variables: 全局变量
            analyze_failures: 是否 AI 分析失败
            stream: 是否流式输出

        Yields:
            进度事件 + 最终结果
        """
        test_case_ids = test_case_ids or []
        global_variables = global_variables or {}

        try:
            # Step 1: 创建执行记录
            yield {"type": "progress", "stage": "init", "message": "创建执行记录..."}

            result = self._storage.create_execution(
                name=f"Agent执行-{len(test_case_ids)}个用例",
                test_case_ids=test_case_ids,
                suite_id=suite_id,
                environment=environment,
                global_variables=global_variables,
            )

            if not result.success:
                yield {"type": "error", "message": f"创建执行记录失败: {result.error}"}
                return

            execution_id = result.execution_id
            yield {
                "type": "progress", "stage": "init",
                "message": f"执行记录 #{execution_id} 已创建，{result.total_cases} 个用例",
                "execution_id": execution_id,
            }

            # Step 2: 首次执行
            yield {
                "type": "progress", "stage": "execution",
                "message": f"正在执行 {result.total_cases} 个用例...",
            }

            exec_start = time.time()
            exec_result = self._execute_suite(execution_id, global_variables)
            exec_duration = int(time.time() - exec_start)

            yield {
                "type": "progress", "stage": "execution",
                "message": (
                    f"执行完成: {exec_result.get('passed',0)}P / "
                    f"{exec_result.get('failed',0)}F / "
                    f"{exec_result.get('skipped',0)}S, "
                    f"耗时 {exec_duration}s"
                ),
                "stats": {
                    "passed": exec_result.get("passed", 0),
                    "failed": exec_result.get("failed", 0),
                    "skipped": exec_result.get("skipped", 0),
                    "duration": exec_duration,
                },
            }

            all_results = exec_result.get("results", [])
            total_passed = exec_result.get("passed", 0)
            total_failed = exec_result.get("failed", 0)
            total_skipped = exec_result.get("skipped", 0)

            # Step 3: 失败分析与重试循环
            retry_count = 0
            while total_failed > 0 and retry_count < max_retries:
                retry_count += 1
                yield {
                    "type": "progress", "stage": "retry",
                    "message": f"第 {retry_count}/{max_retries} 次重试准备中...",
                }

                # AI 分析失败
                failed_cases = [r for r in all_results if r.get("status") == "failed"]
                failure_analysis = {}

                if analyze_failures and failed_cases:
                    yield {
                        "type": "progress", "stage": "analysis",
                        "message": f"AI 正在分析 {len(failed_cases)} 个失败用例...",
                    }
                    failure_analysis = self._analyze(failed_cases)

                    yield {
                        "type": "progress", "stage": "analysis",
                        "message": failure_analysis.get("summary", "分析完成"),
                        "analysis": failure_analysis,
                    }

                retry_cases = failure_analysis.get("retry_worthy_cases", [])
                if not retry_cases:
                    yield {
                        "type": "progress", "stage": "retry",
                        "message": "AI 判断无需重试，跳过",
                    }
                    break

                # 执行重试
                retry_case_ids = [c["case_id"] for c in retry_cases]
                yield {
                    "type": "progress", "stage": "retry",
                    "message": f"重试 {len(retry_case_ids)} 个用例...",
                }

                retry_result = self._storage.create_execution(
                    name=f"重试-{retry_count}-exec_{execution_id}",
                    test_case_ids=retry_case_ids,
                    suite_id=suite_id,
                    environment=environment,
                )

                if retry_result.success:
                    retry_exec = self._execute_suite(
                        retry_result.execution_id, global_variables,
                    )

                    merged = self._merge_results(
                        {"passed": total_passed, "failed": total_failed, "skipped": total_skipped,
                         "total": len(all_results), "results": all_results},
                        retry_exec,
                        execution_id,
                    )

                    total_passed = merged["passed"]
                    total_failed = merged["failed"]
                    total_skipped = merged["skipped"]
                    all_results = merged["results"]

                    yield {
                        "type": "progress", "stage": "retry",
                        "message": (
                            f"重试完成: {retry_exec.get('passed',0)}P / "
                            f"{retry_exec.get('failed',0)}F"
                        ),
                    }

            # Step 4: 最终统计
            final_status = "completed" if total_failed == 0 else (
                "partial" if total_passed > 0 else "failed"
            )
            final_stats = {
                "total": len(all_results),
                "passed": total_passed,
                "failed": total_failed,
                "skipped": total_skipped,
                "duration": exec_duration,
                "retries": retry_count,
            }

            self._storage.update_status(
                execution_id=execution_id,
                status=final_status,
                results=all_results,
                passed=total_passed,
                failed=total_failed,
                skipped=total_skipped,
                duration=exec_duration,
            )

            # Step 5: 执行总结
            yield {"type": "progress", "stage": "summary", "message": "AI 生成执行总结..."}
            execution_summary = {}
            if analyze_failures and len(all_results) > 0:
                try:
                    execution_summary = self._summarize({
                        "total": len(all_results),
                        "passed": total_passed,
                        "failed": total_failed,
                        "skipped": total_skipped,
                        "duration": exec_duration,
                        "results": all_results,
                    })
                except Exception:
                    pass

            yield {
                "type": "progress", "stage": "summary",
                "message": "总结完成",
                "summary": execution_summary,
            }

            # Step 6: Allure 报告
            yield {"type": "progress", "stage": "report", "message": "生成 Allure 报告..."}
            report = self._allure.build_report_bundle(
                execution_id=execution_id,
                execution_results=all_results,
                execution_stats=final_stats,
            )

            yield {
                "type": "progress", "stage": "report",
                "message": f"报告类型: {report['report_type']}",
                "report": report,
            }

            # Step 7: 最终结果
            yield {
                "type": "done",
                "execution_id": execution_id,
                "status": final_status,
                "stats": final_stats,
                "summary": execution_summary,
                "report": report,
                "results": all_results[:30],
            }

        except Exception as e:
            logger.exception(f"[ExecutionAgent] 执行失败: {e}")
            yield {"type": "error", "message": str(e)}

    # ============================================================
    # 核心执行
    # ============================================================

    def _execute_suite(self, execution_id: int, global_variables: dict = None) -> dict:
        """
        调用 TestExecutionEngine 执行测试

        Returns:
            {"success": bool, "passed": int, "failed": int, "skipped": int,
             "total": int, "duration": int, "results": [...], "error": str}
        """
        from execution.engine import TestExecutionEngine

        try:
            engine = TestExecutionEngine(
                execution_id=execution_id,
                global_variables=global_variables or {},
            )
            exec_obj = engine.execute()

            results = exec_obj.execution_results or []
            return {
                "success": True,
                "passed": exec_obj.passed_count,
                "failed": exec_obj.failed_count,
                "skipped": exec_obj.skipped_count,
                "total": exec_obj.total_count,
                "duration": exec_obj.duration,
                "results": results,
            }

        except Exception as e:
            logger.exception(f"[ExecutionAgent] 执行异常: {e}")
            self._storage.update_log(execution_id, f"[错误] {e}")
            return {
                "success": False,
                "passed": 0, "failed": 0, "skipped": 0,
                "total": 0, "duration": 0,
                "results": [],
                "error": str(e),
            }

    def _merge_results(self, original: dict, retry: dict, execution_id: int) -> dict:
        """
        合并原始结果和重试结果

        规则：重试成功的替换原来的失败记录
        """
        orig_results = {r.get("case_id"): r for r in (original.get("results") or [])}
        retry_results = retry.get("results") or []

        for r in retry_results:
            cid = r.get("case_id")
            if cid in orig_results and orig_results[cid].get("status") == "failed":
                if r.get("status") == "passed":
                    orig_results[cid] = r

        merged = list(orig_results.values())
        return {
            "passed": sum(1 for r in merged if r.get("status") == "passed"),
            "failed": sum(1 for r in merged if r.get("status") == "failed"),
            "skipped": sum(1 for r in merged if r.get("status") == "skipped"),
            "total": len(merged),
            "results": merged,
        }

    # ============================================================
    # AI 分析
    # ============================================================

    def _analyze(self, failed_cases: List[Dict]) -> Dict:
        """
        AI 分析失败用例

        Returns:
            {
                "analyses": [...],
                "summary": str,
                "retry_worthy_cases": [{"case_id": int, "suggestion": str}],
            }
        """
        if not failed_cases:
            return {"analyses": [], "summary": "", "retry_worthy_cases": []}

        # 构建失败详情文本
        details_lines = []
        for i, c in enumerate(failed_cases[:10]):  # 最多分析10个
            details_lines.append(
                f"[{i+1}] {c.get('title', '未知')}\n"
                f"    方法: {c.get('method', 'GET')} {c.get('api_endpoint', '')}\n"
                f"    错误: {c.get('error', '')}\n"
                f"    断言错误: {json.dumps(c.get('assertion_errors', []), ensure_ascii=False)}\n"
                f"    响应码: {c.get('response_status_code', 'N/A')}"
            )

        user_prompt = FAILURE_ANALYSIS_USER.format(
            case_details="\n\n".join(details_lines)
        )

        try:
            response = self.ask_llm(
                prompt=user_prompt,
                context={"system": FAILURE_ANALYSIS_SYSTEM},
            )
            analysis = self._parse_json(response)

            # 提取值得重试的用例
            retry_worthy = []
            analyses = analysis.get("analyses", [])
            for i, a in enumerate(analyses):
                if a.get("retry_worth") and i < len(failed_cases):
                    retry_worthy.append({
                        "case_id": failed_cases[i].get("case_id"),
                        "suggestion": a.get("suggestion", ""),
                    })

            return {
                "analyses": analyses,
                "summary": analysis.get("summary", ""),
                "retry_worthy_cases": retry_worthy,
            }

        except Exception as e:
            logger.warning(f"[ExecutionAgent] AI 分析失败: {e}")
            # 回退：所有失败用例都尝试重试一次
            return {
                "analyses": [],
                "summary": f"AI 分析失败({e})，默认重试所有失败用例",
                "retry_worthy_cases": [
                    {"case_id": c.get("case_id"),
                     "suggestion": "默认重试"}
                    for c in failed_cases
                ],
            }

    def _summarize(self, exec_result: dict) -> dict:
        """
        AI 生成执行总结
        """
        total = exec_result.get("total", 0)
        passed = exec_result.get("passed", 0)
        failed = exec_result.get("failed", 0)
        skipped = exec_result.get("skipped", 0)
        duration = exec_result.get("duration", 0)

        if total == 0:
            return {"overall": {"pass_rate": "N/A", "grade": "N/A", "health_status": "unknown"}}

        # 失败详情
        failed_cases = [r for r in exec_result.get("results", []) if r.get("status") == "failed"]
        failed_summaries = []
        for fc in failed_cases[:10]:
            failed_summaries.append(
                f"- {fc.get('title','未知')}: {fc.get('error') or str(fc.get('assertion_errors',[]))}"
            )

        user_prompt = EXECUTION_SUMMARY_USER.format(
            total_count=total,
            passed_count=passed,
            failed_count=failed,
            skipped_count=skipped,
            duration=duration,
            failed_details="\n".join(failed_summaries) if failed_summaries else "无",
        )

        try:
            response = self.ask_llm(
                prompt=user_prompt,
                context={"system": EXECUTION_SUMMARY_SYSTEM},
            )
            return self._parse_json(response)
        except Exception as e:
            logger.warning(f"[ExecutionAgent] 总结生成失败: {e}")
            pass_rate = f"{passed/total*100:.1f}%" if total > 0 else "0%"
            return {
                "overall": {
                    "pass_rate": pass_rate,
                    "grade": self._grade(passed, total),
                    "health_status": "healthy" if failed == 0 else "warning",
                },
                "failure_clusters": [],
                "recommendations": [],
                "risk_alerts": [],
            }

    @staticmethod
    def _grade(passed: int, total: int) -> str:
        """根据通过率计算等级"""
        if total == 0:
            return "N/A"
        rate = passed / total
        if rate >= 0.95:
            return "A"
        elif rate >= 0.80:
            return "B"
        elif rate >= 0.60:
            return "C"
        elif rate >= 0.40:
            return "D"
        return "F"

    # ============================================================
    # 工具方法
    # ============================================================

    @staticmethod
    def _parse_json(text: str) -> dict:
        """容错 JSON 解析"""
        # 提取 markdown 代码块
        code_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
        if code_match:
            text = code_match.group(1)

        # 尝试直接解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 提取花括号
        brace_match = re.search(r'\{[\s\S]*\}', text)
        if brace_match:
            try:
                return json.loads(brace_match.group(0))
            except json.JSONDecodeError:
                pass

        logger.warning(f"[ExecutionAgent] JSON 解析失败: {text[:200]}")
        return {}

    def get_tools(self) -> List[dict]:
        return [
            self._storage.to_openai_function(),
            self._allure.to_openai_function(),
        ]


# 工厂函数
def create_execution_agent(user_id: int = None) -> ExecutionEngineAgent:
    return ExecutionEngineAgent(user_id=user_id)
