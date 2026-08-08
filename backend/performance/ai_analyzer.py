"""
性能测试 AI 诊断器
压测完成后，调用 LLM 分析指标数据，生成结构化的执行总结（exec_summary）
"""
import json
import logging
import threading
from typing import Optional
from django.utils import timezone

logger = logging.getLogger(__name__)


_PERF_ANALYSIS_PROMPT = """你是一位资深性能测试专家。请分析以下压测结果，输出结构化 JSON。

## 压测数据
- 测试类型: {test_type}
- 目标URL: {target_url} ({method})
- 并发用户数: {users}
- 持续时间: {duration}s
- 总请求数: {total_requests}
- QPS: {requests_per_second}
- 失败数: {failures}（失败率: {failure_rate:.2%}）
- 平均响应: {avg_response_time}ms
- P50: {p50_response_time}ms | P90: {p90_response_time}ms | P95: {p95_response_time}ms | P99: {p99_response_time}ms
- 最小响应: {min_response_time}ms | 最大响应: {max_response_time}ms
- 阈值通过: {thresholds_passed}
- 阈值违规: {threshold_errors}

{timeline_summary}

## 输出要求
请严格输出以下 JSON 格式（不要包含 markdown 代码块标记）：

{{
  "score": <0-100 综合评分>,
  "summary": "<一句话总结，中文，30字以内>",
  "fullSummary": "<详细总结，100字以内>",
  "issues": [
    {{"severity": "error|warning|info", "title": "<问题标题>", "desc": "<问题描述>", "suggestion": "<优化建议>"}}
  ],
  "recommendations": ["<建议1>", "<建议2>", "<建议3>"]
}}

注意：
- score 根据响应时间、失败率、QPS 稳定性综合给分
- 如果全部达标赋值高分(85+)，有轻微问题70-84，严重问题<70
- issues 最多3条，按严重程度排序
- recommendations 给出具体可操作的优化方向
"""


class PerfAIAnalyzer:
    """性能测试 AI 诊断器"""

    @staticmethod
    def analyze(execution) -> Optional[dict]:
        """
        分析执行结果并返回结构化诊断
        失败时返回 None（不阻塞主流程）
        """
        try:
            test_case = execution.test_case
            timeline = execution.metrics_timeline or []

            # 构建时间线摘要
            if timeline:
                rps_vals = [p.get('rps', 0) for p in timeline]
                p95_vals = [p.get('p95', 0) for p in timeline]
                timeline_summary = (
                    f"- 时间序列: {len(timeline)} 个采样点\n"
                    f"- QPS范围: {min(rps_vals):.0f} ~ {max(rps_vals):.0f}\n"
                    f"- P95范围: {min(p95_vals):.0f}ms ~ {max(p95_vals):.0f}ms"
                )
            else:
                timeline_summary = "- 无时间序列数据"

            total_req = execution.total_requests or 0
            fail_rate = execution.failures / max(total_req, 1)

            prompt = _PERF_ANALYSIS_PROMPT.format(
                test_type=execution.test_type or 'baseline',
                target_url=test_case.target_url,
                method=test_case.method,
                users=execution.users,
                duration=execution.duration,
                total_requests=total_req,
                requests_per_second=execution.requests_per_second or 0,
                failures=execution.failures or 0,
                failure_rate=fail_rate,
                avg_response_time=execution.avg_response_time or 0,
                p50_response_time=execution.p50_response_time or 0,
                p90_response_time=execution.p90_response_time or 0,
                p95_response_time=execution.p95_response_time or 0,
                p99_response_time=execution.p99_response_time or 0,
                min_response_time=execution.min_response_time or 0,
                max_response_time=execution.max_response_time or 0,
                thresholds_passed=execution.thresholds_passed,
                threshold_errors=execution.threshold_errors or [],
                timeline_summary=timeline_summary,
            )

            from core.llm_provider import LLMProviderFactory
            llm = LLMProviderFactory.create('dashscope')
            response = llm.chat(
                [{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=800,
            )

            # 解析 AI 返回的 JSON
            result = PerfAIAnalyzer._parse_response(response)

            # 保存到执行记录
            execution.exec_summary = result
            execution.save(update_fields=['exec_summary'])

            logger.info(f"AI 性能诊断完成，评分: {result.get('score', '?')}")
            return result

        except Exception as e:
            logger.warning(f"AI 性能诊断失败: {e}")
            return None

    @staticmethod
    def analyze_async(execution):
        """异步执行 AI 诊断（在独立线程中）"""
        def _run():
            PerfAIAnalyzer.analyze(execution)
        t = threading.Thread(target=_run, daemon=True)
        t.start()

    @staticmethod
    def _parse_response(response: str) -> dict:
        """解析 AI 返回的 JSON"""
        # 清理可能的 markdown 代码块标记
        text = response.strip()
        if text.startswith('```'):
            # 移除 ```json 和结尾的 ```
            lines = text.split('\n')
            lines = lines[1:] if lines[0].startswith('```') else lines
            if lines[-1].strip() == '```':
                lines = lines[:-1]
            text = '\n'.join(lines)

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # 尝试提取第一个 { 到最后一个 } 之间的内容
            start = text.find('{')
            end = text.rfind('}')
            if start >= 0 and end > start:
                try:
                    return json.loads(text[start:end + 1])
                except json.JSONDecodeError:
                    pass
            logger.warning(f"无法解析 AI 响应为 JSON: {text[:200]}")
            return PerfAIAnalyzer._fallback_analysis()

    @staticmethod
    def _fallback_analysis() -> dict:
        """AI 调用失败时的降级分析"""
        return {
            "score": None,
            "summary": "AI 诊断暂不可用",
            "fullSummary": "AI 服务暂时无法提供分析，请查看下方指标数据自行判断。",
            "issues": [],
            "recommendations": ["请根据上方指标曲线和阈值结果自行评估性能表现。"],
        }
