"""RAG 问答插件（P2 新增，证明业务插件化横向扩展能力）。

链路：将用户问题经混合检索召回上下文，再让 LLM 基于上下文作答。
全程只调中台原语（embedding/网关/检索），不直连第三方（红线 #1）。
"""
from __future__ import annotations

from harness_core.llm.base import ChatMessage
from harness_core.llm.gateway import GatewayContext, gateway
from harness_core.plugins import (
    BasePlugin,
    PluginContext,
    PluginResult,
    register_plugin,
)
from harness_core.rag.chunker import split_text
from harness_core.rag.retriever import retriever

_SYSTEM_PROMPT = (
    "你是企业知识库助手。请仅基于下面提供的【上下文】回答问题，"
    "若上下文不足以回答，明确说明无法回答，不要编造。"
)


@register_plugin
class RagQaPlugin(BasePlugin):
    key = "rag_qa"
    name = "RAG 知识库问答"
    sandbox_required = False

    async def execute(self, ctx: PluginContext, payload: dict) -> PluginResult:
        question = payload.get("question", "")
        if not question:
            return PluginResult(success=False, error="question 不能为空")

        # 1. 混合检索（向量 + 关键词）
        chunks = split_text(payload.get("context", ""))
        corpus = [c.text for c in chunks]
        retriever.index_corpus(corpus)
        # 向量召回（演示：用 chunk 自身索引模拟命中排序）
        vecs = await retriever.embed(corpus[:1] or [question])
        vector_hits = list(enumerate([1.0] * len(corpus)))  # P2 简化：全量候选
        hits = retriever.hybrid_search(question, vector_hits, top_k=3)
        context_text = "\n---\n".join(h.text for h in hits) or "（无可用上下文）"

        # 2. LLM 基于上下文作答
        gctx = GatewayContext(
            tenant_id=ctx.tenant_id,
            agent_id=ctx.agent_id,
            trace_id=ctx.trace_id,
            model_preference=ctx.model or "deepseek-chat",
        )
        messages = [
            ChatMessage(role="system", content=_SYSTEM_PROMPT),
            ChatMessage(role="user", content=f"【上下文】\n{context_text}\n\n【问题】{question}"),
        ]
        resp = await gateway.chat(gctx, messages, temperature=0.3, max_tokens=1024)
        return PluginResult(
            success=True,
            data={
                "question": question,
                "answer": resp.content,
                "retrieved": [h.text for h in hits],
                "trace_id": ctx.trace_id,
            },
        )
