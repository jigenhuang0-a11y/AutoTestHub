"""
评估闭环（Evaluation Loop）— AI 测试平台核心质量闸门

设计（基于循环工程）：
  生成回答 → evaluate() 评分
    → score ≥ threshold：通过，写入长期记忆（仅此情况沉淀）
    → score <  threshold：把 issues 反馈回生成，重新生成（循环工程）
        → 未超 max_iterations：继续循环
        → 超过 max_iterations 仍不达标：标记 needs_human，推送飞书人工协同卡片

可调参数：
  - max_iterations：循环重生成次数上限（默认 3）
  - threshold：通过阈值（默认 0.7）
  - enable_eval：是否开启评估闭环（关闭时退化为原逻辑，直接输出）

该模块不绑定具体对话模式，answer_stream / chat_stream 都可复用。
"""
from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from app.tools.evaluate_run import evaluate
from app.core.webhook_notifier import notify_human_review
from app.core.hallucination_judge import judge_output
from app.core.eval_store import get_eval_store
from app.core.eval_event_store import get_eval_event_store

logger = logging.getLogger(__name__)

DEFAULT_MAX_ITERATIONS = 3
DEFAULT_THRESHOLD = 0.7

# 测试场景默认评测维度（AI 测试平台专用）
TESTING_CRITERIA = [
    "用例覆盖度：是否覆盖正常/边界/异常场景，关键路径是否遗漏",
    "断言与校验有效性：是否包含可验证的预期结果、断言或检查点",
    "可执行性：步骤是否清晰、可直接转化为自动化脚本或手工测试动作",
    "与参考材料一致性（忠实度）：是否严格基于检索/参考内容，未编造不存在的接口/字段/结论",
    "清晰度与规范性：术语准确、结构清晰、符合测试文档规范",
]


@dataclass
class EvalResult:
    """一次评估闭环的最终结果"""
    final_answer: str = ""
    score: float = 0.0
    issues: List[str] = field(default_factory=list)
    iterations: int = 0
    passed: bool = False
    needs_human: bool = False        # 循环耗尽仍不达标，转人工协同
    eval_summary: str = ""
    criteria: List[str] = field(default_factory=list)
    trace_id: Optional[str] = None           # 关联的 Langfuse trace_id
    judge: Optional[Dict] = None             # 五维 Judge 结果（hallucination_judge）
    judge_record_id: Optional[str] = None    # 写入 EvalStore 的记录 id
    trace_steps: List[Dict] = field(default_factory=list)  # 链路步骤，最终回写 EvalEvent


def _make_evaluator(criteria: Optional[List[str]] = None) -> Callable:
    """构造一个评分器：调用 evaluate 工具，失败时不阻塞主流程（返回最低分）。"""
    def _score(content: str, reference: str = "") -> Dict:
        try:
            resp = evaluate(content=content, reference=reference, criteria=criteria)
        except Exception as e:
            logger.error(f"[EvalLoop] 评测调用异常: {e}")
            return {"score": 0.0, "issues": [f"评测失败: {e}"], "summary": "评测异常，已降级处理"}
        if resp.get("status") != "success":
            return {"score": 0.0, "issues": [resp.get("error", "评测失败")], "summary": "评测失败"}
        data = resp.get("data", {})
        return {
            "score": float(data.get("score", 0.0)),
            "issues": data.get("issues", []) or [],
            "summary": data.get("summary", ""),
            "criteria": data.get("criteria", []),
        }
    return _score


def run_eval_loop(
    question: str,
    candidates: List[str],
    reference: str = "",
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
    threshold: float = DEFAULT_THRESHOLD,
    enable_eval: bool = True,
    regenerate_fn: Optional[Callable[[str], str]] = None,
    sink_if_passed: Optional[Callable[[str], None]] = None,
    human_review_ctx: Optional[Dict] = None,
    criteria: Optional[List[str]] = None,
    feature: str = "agent_loop",
    trace_id: Optional[str] = None,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    retrieved_docs: Optional[List[Dict]] = None,
    model: Optional[str] = None,
    latency_ms: Optional[int] = None,
) -> EvalResult:
    """
    评估闭环主入口。

    Args:
        question:        原始用户问题（用于人工协同卡片 & 上下文）
        candidates:      候选回答列表（已生成的回答，按顺序尝试评估）
        reference:       参考答案（可选，RAG 场景下可用检索片段）
        max_iterations:  循环重生成上限
        threshold:       通过阈值
        enable_eval:     是否开启评估闭环
        regenerate_fn:   重生成函数，接收 issues 文本，返回新回答（循环工程）
        sink_if_passed:  评估通过时的回调（沉淀长期记忆）
        human_review_ctx: 人工协同上下文（含 user_id / mode 等），非空才推飞书
        feature:         业务模块标识（写入评估中心，如 ai_testcase / knowledge_chat / agent_loop）
        question_feature: 兼容别名
        trace_id:        关联的 Langfuse trace_id；为空时自动生成，使每次 Loop 都可被全链路追踪
        user_id/session_id: 追踪字段

    Returns:
        EvalResult（含 judge 五维评分与 EvalStore 记录 id）
    """
    result = EvalResult()
    if not candidates:
        return result

    # 不开启评估：直接取最后一个候选，不沉淀、不推送
    if not enable_eval:
        result.final_answer = candidates[-1]
        result.iterations = 1
        result.passed = True
        result.trace_id = trace_id or str(uuid.uuid4())
        result.trace_steps = trace_steps or []
        return result

    # 关联/创建 Langfuse trace：让 Agent Loop 的每一次评估都可被全链路追踪
    if not trace_id:
        trace_id = str(uuid.uuid4())
    result.trace_id = trace_id
    result.trace_steps = trace_steps or []

    # 默认测试场景维度；RAG/知识库场景（有 reference）强制使用测试维度
    effective_criteria = criteria or TESTING_CRITERIA
    scorer = _make_evaluator(effective_criteria)

    # 当前所有候选答案（首轮由调用方传入，后续轮由 regenerate_fn 生成）
    current_candidates = list(candidates)
    best_answer = current_candidates[0]
    best_score = -1.0
    best_issues: List[str] = []

    # 循环工程：最多 max_iterations 轮
    for iteration in range(1, max_iterations + 1):
        # 取出本轮待评估的答案（首次用首候选，后续用 regenerate 结果）
        answer = current_candidates[iteration - 1] if iteration <= len(current_candidates) else current_candidates[-1]

        ev = scorer(answer, reference)
        score = float(ev.get("score", 0.0))
        issues = ev.get("issues", []) or []
        logger.info(f"[EvalLoop] 第 {iteration} 轮 score={score:.2f}, issues={len(issues)}")

        if score > best_score:
            best_score = score
            best_answer = answer
            best_issues = issues

        result.iterations = iteration
        result.eval_summary = ev.get("summary", "")
        if ev.get("criteria"):
            result.criteria = ev["criteria"]
        else:
            result.criteria = effective_criteria

        if score >= threshold:
            result.final_answer = answer
            result.score = score
            result.issues = issues
            result.passed = True
            if sink_if_passed:
                try:
                    sink_if_passed(answer)
                except Exception as e:
                    logger.error(f"[EvalLoop] 长期记忆沉淀失败: {e}")
            # 通过即退出循环，对最终答案做五维 Judge 并写入评估中心
            _run_judge_and_persist(
                result, question, answer, reference, feature, trace_id, user_id, session_id,
                retrieved_docs=retrieved_docs, model=model, latency_ms=latency_ms,
                trace_steps=result.trace_steps,
            )
            return result

        # 未达标且还有重生成机会：调用 regenerate_fn 生成下一轮答案
        if regenerate_fn and iteration < max_iterations:
            try:
                new_answer = regenerate_fn(issues)
                if isinstance(new_answer, str) and new_answer.strip():
                    current_candidates.append(new_answer)
                    continue
            except Exception as e:
                logger.error(f"[EvalLoop] 重生成失败: {e}")
            # 重生成失败则不再继续循环
            break

    # 循环耗尽仍未达标（或没有重生成能力）
    result.final_answer = best_answer
    result.score = best_score if best_score >= 0 else 0.0
    result.issues = best_issues
    result.passed = best_score >= threshold
    result.needs_human = not result.passed
    result.criteria = effective_criteria

    # 不论达标与否，都对最终答案做五维 Judge 并写入评估中心（供全链路评测中心看板）
    _run_judge_and_persist(
        result, question, best_answer, reference, feature, trace_id, user_id, session_id,
        retrieved_docs=retrieved_docs, model=model, latency_ms=latency_ms,
        trace_steps=result.trace_steps,
    )

    if result.needs_human and human_review_ctx:
        try:
            notify_human_review(
                question=question,
                best_answer=best_answer,
                score=result.score,
                issues=result.issues,
                iterations=result.iterations,
                ctx=human_review_ctx,
                criteria=effective_criteria,
            )
        except Exception as e:
            logger.error(f"[EvalLoop] 飞书人工协同推送失败: {e}")

    return result


def _run_judge_and_persist(
    result: EvalResult,
    question: str,
    answer: str,
    reference: str,
    feature: str,
    trace_id: Optional[str],
    user_id: Optional[str],
    session_id: Optional[str],
    retrieved_docs: Optional[List[Dict]] = None,
    model: Optional[str] = None,
    latency_ms: Optional[int] = None,
    token_usage: Optional[int] = None,
    trace_steps: Optional[List[Dict]] = None,
) -> None:
    """对最终答案执行五维 Judge 评分，写入 EvalStore 并回传 Langfuse trace。

    失败仅记日志，绝不阻塞主业务（Agent Loop 的吞吐优先）。
    """
    try:
        judge = judge_output(
            input_text=question,
            output_text=answer,
            reference=reference,
            trace_id=trace_id,
            feature=feature,
            user_id=user_id,
            session_id=session_id,
        )
        record = judge.to_dict()
        record["feature"] = feature
        record["input_text"] = question[:1000]
        record["output_text"] = answer[:1000]
        record["reference"] = (reference or "")[:2000]
        # 链路追踪增强字段（RAG 回放 / 调用开销）
        if retrieved_docs:
            record["retrieved_docs"] = retrieved_docs[:10]
        if model:
            record["model"] = model
        if latency_ms is not None:
            record["latency_ms"] = latency_ms
        if token_usage is not None:
            record["token_usage"] = token_usage
        record_id = get_eval_store().save(record)
        # 把 Judge 结果精确回写到 EvalEventStore 的对应 trace_id 事件
        try:
            judge_step = {
                "step_id": f"step-judge-{trace_id or uuid.uuid4()}",
                "type": "judge",
                "title": "Judge 评分",
                "status": "completed",
                "start_time_ms": int(time.time() * 1000),
                "end_time_ms": int(time.time() * 1000),
                "detail": f"综合分 {judge.overall}，结论：{judge.summary}",
                "metadata": {
                    "overall": judge.overall,
                    "dimension_scores": record.get("dimension_scores", {}),
                    "issues": record.get("issues", []),
                    "summary": judge.summary,
                },
            }
            if trace_steps is not None:
                trace_steps.append(judge_step)
            updated_event_id = get_eval_event_store().update_by_trace_id(
                trace_id=trace_id or "",
                judge=judge.to_dict(),
                dimension_scores=record.get("dimension_scores", {}),
                issues=record.get("issues", []),
                trace_steps=trace_steps,
            )
            if not updated_event_id:
                # 兜底：若 RAG/chat 主流程未预先写入事件，则 Judge 完成后直接新增一条
                from app.core.eval_event_store import build_event
                get_eval_event_store().add(build_event(
                    feature=feature,
                    task_type=feature,
                    model=model or "unknown",
                    provider="deepseek",
                    input_text=question,
                    output_text=answer,
                    latency_ms=latency_ms or 0,
                    trace_id=trace_id,
                    retrieved_docs=retrieved_docs or [],
                    trace_steps=trace_steps,
                    judge=judge.to_dict(),
                    status="completed",
                ))
                logger.info(f"[EvalLoop] trace_id={trace_id} 无前置事件，已兜底新增 Judge 事件")
        except Exception as e:
            logger.warning(f"[EvalLoop] 关联 EvalEvent 失败（已忽略）: {e}")
        # result 可能来自后台异步路径（None），仅在非空时回填
        if result is not None:
            result.judge = judge.to_dict()
            result.judge_record_id = record_id
        logger.info(
            f"[EvalLoop] Judge 完成 overall={judge.overall}, record={record_id}, trace={trace_id}"
        )
    except Exception as e:
        logger.warning(f"[EvalLoop] Judge/持久化失败（已忽略）: {e}")
