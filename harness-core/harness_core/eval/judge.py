"""全链路评测 - LLM-as-Judge 自动打分（P2）。

对一次 Agent 执行的产出（如生成的测试用例、RAG 答案），
由裁判模型依据 rubric 维度自动评分，结果写入 Trace 供监控大屏。

P2 实现单轮裁判；P3 可多裁判交叉 + 人类反馈回流。
"""
from __future__ import annotations

import json

from harness_core.llm.base import ChatMessage
from harness_core.llm.gateway import GatewayContext, gateway
from harness_core.logging import logger

_JUDGE_PROMPT = (
    "你是严格的测试质量评审官。请基于【任务】与【产出】，按维度打分(1-5)并给总结。\n"
    "维度：覆盖度(coverage)、清晰度(clarity)、可执行性(executability)。\n"
    "只输出 JSON：{\"coverage\":int,\"clarity\":int,\"executability\":int,\"summary\":\"...\"}"
)


async def judge(
    tenant_id: int, task: str, output: str, *, trace_id: str = "", model: str = "deepseek-chat"
) -> dict:
    gctx = GatewayContext(
        tenant_id=tenant_id, trace_id=trace_id, model_preference=model
    )
    messages = [
        ChatMessage(role="system", content=_JUDGE_PROMPT),
        ChatMessage(role="user", content=f"【任务】{task}\n\n【产出】{output}"),
    ]
    try:
        resp = await gateway.chat(gctx, messages, temperature=0.1, max_tokens=512)
        verdict = json.loads(resp.content)
        verdict.setdefault("score", round(
            (verdict.get("coverage", 0) + verdict.get("clarity", 0) + verdict.get("executability", 0)) / 3, 2
        ))
        return verdict
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[eval] 评测失败: {e}")
        return {"coverage": 0, "clarity": 0, "executability": 0, "score": 0, "summary": f"评测异常: {e}"}
