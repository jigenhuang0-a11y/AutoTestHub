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
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from app.tools.evaluate_run import evaluate
from app.core.webhook_notifier import notify_human_review

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

    Returns:
        EvalResult
    """
    result = EvalResult()
    if not candidates:
        return result

    # 不开启评估：直接取最后一个候选，不沉淀、不推送
    if not enable_eval:
        result.final_answer = candidates[-1]
        result.iterations = 1
        result.passed = True
        return result

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
