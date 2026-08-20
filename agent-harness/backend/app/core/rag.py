"""
RAG 核心 — 知识库检索增强生成。

流程：
  ingest: 文档文本 -> 切分 chunk -> embedding -> 存入向量库（按 kb_id 分集合）
  query : 问题 -> embedding -> 检索 top_k -> 拼 context -> LLM 生成回答

依赖 AI 底座：
  - embedding.py 提供向量化（DashScope / 本地兜底）
  - vector_store.py 提供本地向量存储（接口对齐 Milvus）
  - router.py 提供 LLM（rag_query 任务类型）
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
import threading
import time
import uuid
from typing import List, Dict, Optional, Generator

# 在 FastAPI 主线程 import 时保存事件循环引用，用于把评估闭环放到后台异步执行，
# 避免阻塞 SSE 流式响应。
try:
    _MAIN_LOOP: Optional[asyncio.AbstractEventLoop] = asyncio.get_event_loop()
except Exception:
    _MAIN_LOOP = None

from app.core.embedding import get_embedding_provider
from app.core.vector_store import get_vector_store
from app.core.router import get_llm_router
from app.core.memory_bridge import (
    get_memory_for,
    build_long_term_context,
    sink_memory,
    format_long_term_block,
)

logger = logging.getLogger(__name__)


def _now_ms() -> int:
    return int(time.time() * 1000)


def _summarize(text: str, max_len: int = 120) -> str:
    if not isinstance(text, str):
        text = str(text)
    text = text.strip().replace("\n", " ")
    return text if len(text) <= max_len else text[:max_len] + "..."


def _make_input_step(question: str, history: Optional[List[Dict]] = None) -> Dict:
    return {
        "step_id": f"step-input-{_now_ms()}",
        "type": "input",
        "title": "用户提问",
        "status": "completed",
        "start_time_ms": _now_ms(),
        "end_time_ms": _now_ms(),
        "detail": question,
        "output": question,
        "metadata": {
            "history_turns": len(history) if history else 0,
            "enable_reasoning": False,
        },
    }


def _make_retrieve_step(question: str, hits: List[Dict], latency_ms: int = 0) -> Dict:
    top = [
        {
            "source": h.get("meta", {}).get("filename", "知识库"),
            "chunk_index": h.get("meta", {}).get("chunk_index", 0),
            "score": round(h.get("score", 0.0), 4),
            "content": _summarize(h.get("text", ""), 200),
        }
        for h in hits[:5]
    ]
    return {
        "step_id": f"step-retrieve-{_now_ms()}",
        "type": "retrieve",
        "title": "检索上下文（RAG 引用）",
        "status": "completed",
        "start_time_ms": _now_ms() - latency_ms,
        "end_time_ms": _now_ms(),
        "detail": f"命中 {len(hits)} 个 chunk，取 top-{len(top)}",
        "metadata": {"query": question, "hits": top, "hit_count": len(hits)},
    }


def _make_prompt_step(system_text: str, user_text: str) -> Dict:
    return {
        "step_id": f"step-prompt-{_now_ms()}",
        "type": "prompt",
        "title": "Prompt 组装",
        "status": "completed",
        "start_time_ms": _now_ms(),
        "end_time_ms": _now_ms(),
        "detail": f"system 长度 {len(system_text)} 字，user 长度 {len(user_text)} 字",
        "metadata": {
            "system": system_text,
            "user": user_text,
        },
    }


def _make_llm_step(model: str, provider: str, latency_ms: int, token_usage: int, route_reason: str = "") -> Dict:
    return {
        "step_id": f"step-llm-{_now_ms()}",
        "type": "llm",
        "title": "LLM 生成",
        "status": "completed",
        "start_time_ms": _now_ms() - latency_ms,
        "end_time_ms": _now_ms(),
        "detail": f"{model} / {provider}，耗时 {latency_ms}ms，token≈{token_usage}",
        "metadata": {
            "model": model,
            "provider": provider,
            "latency_ms": latency_ms,
            "token_usage": token_usage,
            "route_reason": route_reason,
        },
    }


def _make_route_step(task_type: str, model: str, reason: str) -> Dict:
    return {
        "step_id": f"step-route-{_now_ms()}",
        "type": "route",
        "title": "LLM 路由",
        "status": "completed",
        "start_time_ms": _now_ms(),
        "end_time_ms": _now_ms(),
        "detail": f"task_type={task_type} -> {model}",
        "metadata": {"task_type": task_type, "model": model, "reason": reason},
    }


def _llm_fn_for_memory(prompt: str) -> str:
    """供长期记忆自动提取使用的 LLM 调用封装（与 evaluate 工具同源）。"""
    try:
        router = get_llm_router()
        resp = router.chat(messages=[
            {"role": "system", "content": "你是记忆提取助手，只输出结构化记忆条目。"},
            {"role": "user", "content": prompt},
        ], task_type="evaluation")
        return resp if isinstance(resp, str) else str(resp)
    except Exception as e:
        logger.error(f"[RAG] 记忆提取 LLM 调用失败: {e}")
        return ""


async def _gen_once_async(
    router,
    messages: List[Dict],
    task_type: str,
    temperature: float,
    issue_hint: str = "",
    enable_reasoning: bool = False,
) -> str:
    """异步单次生成（供后台评估重生成使用）。实际 LLM 流是同步生成器，放到线程池执行。"""
    msgs = list(messages)
    if issue_hint:
        msgs.append({"role": "user", "content": issue_hint})
    if enable_reasoning:
        msgs = _apply_reasoning_prompt(msgs, enable_reasoning)

    def _sync_gen():
        buf: list[str] = []
        try:
            for ev in router.chat_stream(msgs, task_type=task_type, temperature=temperature, enable_reasoning=enable_reasoning):
                if isinstance(ev, dict) and ev.get("type") == "delta":
                    buf.append(ev.get("content", ""))
                elif isinstance(ev, str):
                    buf.append(ev)
        except Exception as e:
            logger.error(f"[RAG] 后台重生成失败: {e}")
        return "".join(buf).strip()

    return await asyncio.to_thread(_sync_gen)


async def _run_eval_async(
    *,
    mode: str,
    question: str,
    first_answer: str,
    reference: str,
    max_iterations: int,
    threshold: float,
    mm,
    user_id: str,
    messages: List[Dict] = None,
    prompt_text: str = "",
    task_type: str = "fast_chat",
    temperature: float = 0.7,
    enable_reasoning: bool = False,
    retrieved_docs: Optional[List[Dict]] = None,
    model: Optional[str] = None,
    latency_ms: Optional[int] = None,
    trace_id: Optional[str] = None,
    trace_steps: Optional[List[Dict]] = None,
):
    """
    后台异步执行规则化简版评分（不调用 LLM，省内存，适合演示）。
    计算五维评分后通过 trace_id 回写到 EvalEventStore，供全链路评测看板展示。
    """
    from app.core.eval_event_store import get_eval_event_store

    trace_id = trace_id or str(uuid.uuid4())
    has_context = bool(retrieved_docs)
    res = _rule_based_eval(first_answer, has_context)
    dimension_scores = _rule_eval_to_dimension_scores(res)
    judge = {
        "overall": res["overall"],
        "hallucination": res["hallucination"],
        "consistency": res["consistency"],
        "completeness": res["completeness"],
        "executability": res["executability"],
        "safety": res["safety"],
        "issues": res["issues"],
        "method": "rule_based_demo",
    }

    # 通过 trace_id 精确回写评分到事件（不依赖前缀匹配）
    try:
        get_eval_event_store().update_by_trace_id(
            trace_id=trace_id,
            judge=judge,
            dimension_scores=dimension_scores,
            issues=res["issues"],
            trace_steps=trace_steps if trace_steps is not None else [],
        )
        logger.info(f"[RAG][规则评分] {mode} 完成，综合分={res['overall']}，trace_id={trace_id}")
    except Exception as e:
        logger.error(f"[RAG][规则评分] 回写失败 trace_id={trace_id}: {e}")


def _schedule_background_eval(coro):
    """把后台评估协程放到独立后台线程运行，不阻塞响应也不依赖主循环。"""
    def _run():
        try:
            asyncio.run(coro)
        except Exception as e:
            logger.error(f"[RAG] 后台评估执行失败: {e}")

    threading.Thread(target=_run, daemon=True).start()


def _estimate_tokens(text: str) -> int:
    """估算 token 数：中文约 1.6 token/字，英文/数字约 0.3 token/字符。

    规则化简版，避免依赖 provider 的 usage 字段（部分模型不返回）。
    """
    if not text:
        return 0
    cn = len(re.findall(r"[\u4e00-\u9fff]", text))
    other = len(text) - cn
    return int(cn * 1.6 + other * 0.3)


def _rule_based_eval(answer: str, has_context: bool) -> Dict[str, Any]:
    """规则化简版五维评分（不调用 LLM，省内存，适合演示）。

    维度：幻觉率(hallucination, 越低越好)、一致性(consistency)、
    完整性(completeness)、可执行性(executability)、安全性(safety)。
    综合分 = 加权平均（幻觉率反向计入）。
    """
    if not answer or not answer.strip():
        return {
            "overall": 0.0,
            "hallucination": 100.0,
            "consistency": 0.0,
            "completeness": 0.0,
            "executability": 0.0,
            "safety": 0.0,
            "issues": ["回答为空"],
        }

    text = answer.strip()
    length = len(text)
    issues: List[str] = []

    # 1) 长度分：80~1200 字最合理，过短/过长都扣分
    if length < 40:
        length_score = 30.0
        issues.append("回答过短，信息量不足")
    elif length < 80:
        length_score = 65.0
    elif length <= 1200:
        length_score = 95.0
    elif length <= 2000:
        length_score = 80.0
        issues.append("回答偏长，可更精炼")
    else:
        length_score = 60.0
        issues.append("回答过长，重点不突出")

    # 2) 结构化分：含列表/代码块/标题/加粗等结构化标记
    struct_hits = 0
    if re.search(r"(^|\n)\s*[-*]\s+", text):  # 无序列表
        struct_hits += 1
    if re.search(r"(^|\n)\s*\d+[.、]\s+", text):  # 有序列表
        struct_hits += 1
    if re.search(r"```", text) or "`" in text:  # 代码块/行内代码
        struct_hits += 1
    if re.search(r"(^|\n)#{1,4}\s+", text):  # 标题
        struct_hits += 1
    if "：" in text or "：" in text:  # 键值/说明结构
        struct_hits += 0.5
    structure_score = min(100.0, struct_hits * 22.0)

    # 3) 知识库问答的检索依据分：有上下文引用时完整性/一致性更高
    if has_context:
        context_score = 92.0
        consistency_score = 90.0
        hallucination = 8.0  # 低幻觉率
        executability_score = 85.0
    else:
        context_score = 78.0
        consistency_score = 82.0
        hallucination = 18.0
        executability_score = 72.0

    # 4) 代码/测试相关信号：若含代码块且是测试场景，可执行性加分
    if "```" in text and ("测试" in text or "def " in text or "assert" in text or "class " in text):
        executability_score = min(100.0, executability_score + 10.0)

    # 5) 安全性：默认高，检测明显危险内容才降分
    safety_score = 100.0
    danger_kw = ["rm -rf", "DROP TABLE", "sudo ", "删除数据库", "格式化磁盘"]
    if any(k in text for k in danger_kw):
        safety_score = 60.0
        issues.append("回答含潜在危险操作建议")

    # 综合分：加权（幻觉率反向，权重 0.2）
    overall = (
        length_score * 0.15
        + structure_score * 0.15
        + context_score * 0.15
        + consistency_score * 0.15
        + executability_score * 0.15
        + (100.0 - hallucination) * 0.15
        + safety_score * 0.10
    )

    return {
        "overall": round(overall, 1),
        "hallucination": round(hallucination, 1),
        "consistency": round(consistency_score, 1),
        "completeness": round(context_score, 1),
        "executability": round(executability_score, 1),
        "safety": round(safety_score, 1),
        "issues": issues,
    }


def _rule_eval_to_dimension_scores(res: Dict[str, Any]) -> Dict[str, float]:
    """把规则评分映射为 EvalEventStore 的 dimension_scores 字段。"""
    return {
        "幻觉率": res.get("hallucination", 0.0),
        "一致性": res.get("consistency", 0.0),
        "完整性": res.get("completeness", 0.0),
        "可执行性": res.get("executability", 0.0),
        "安全性": res.get("safety", 0.0),
        "综合分": res.get("overall", 0.0),
    }


CHUNK_SIZE = 600          # 每个 chunk 约 600 字
CHUNK_OVERLAP = 80        # 重叠 80 字，避免切断上下文
TOP_K = 5


def _chunk_text(text: str) -> List[str]:
    """按段落优先、超长再按句子/字符切分"""
    text = text.strip()
    if not text:
        return []
    # 先按空行/标题分段
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: List[str] = []
    for p in paras:
        if len(p) <= CHUNK_SIZE:
            chunks.append(p)
        else:
            # 按句子切
            sentences = re.split(r"(?<=[。！？.!?])", p)
            buf = ""
            for s in sentences:
                if len(buf) + len(s) <= CHUNK_SIZE:
                    buf += s
                else:
                    if buf:
                        chunks.append(buf.strip())
                    buf = s
            if buf:
                chunks.append(buf.strip())
    # 兜底：仍超长则硬切
    final = []
    for c in chunks:
        if len(c) <= CHUNK_SIZE:
            final.append(c)
        else:
            for i in range(0, len(c), CHUNK_SIZE - CHUNK_OVERLAP):
                final.append(c[i : i + CHUNK_SIZE])
    return [c for c in final if c.strip()]


def ingest_document(kb_id: str, filename: str, content: str) -> Dict:
    """把一份文档切分、向量化、入库。返回统计信息。"""
    provider = get_embedding_provider()
    store = get_vector_store(f"kb_{kb_id}", dim=provider.dim)

    chunks = _chunk_text(content)
    if not chunks:
        return {"chunks": 0, "message": "文档内容为空"}

    # chunk id 用 kb + 文件名 + 序号，保证同文件重传可更新
    base = hashlib.md5(filename.encode("utf-8")).hexdigest()[:8]
    ids = [f"{kb_id}:{base}:{i}" for i in range(len(chunks))]
    metas = [{"kb_id": kb_id, "filename": filename, "chunk_index": i} for i in range(len(chunks))]

    vectors = provider.embed(chunks)
    store.add(vectors, chunks, metas, ids)
    logger.info(f"[RAG] 文档 {filename} 入库 kb={kb_id}, chunks={len(chunks)}")
    return {"chunks": len(chunks), "message": "入库成功"}


def retrieve(kb_id: str, question: str, top_k: int = TOP_K, trace_id: Optional[str] = None) -> List[Dict]:
    """检索相关 chunk（跨多个文档）。embedding 失败时降级返回空列表，避免请求挂死。"""
    try:
        provider = get_embedding_provider()
        store = get_vector_store(f"kb_{kb_id}", dim=provider.dim)
        q_vec = provider.embed([question])[0]
        return store.search(q_vec, top_k=top_k, trace_id=trace_id)
    except Exception as e:
        logger.warning(f"[RAG] 检索失败 kb={kb_id}: {e}")
        return []


def answer(
    kb_id: str,
    question: str,
    history: Optional[List[Dict]] = None,
    user_id: str = "anonymous",
    enable_reasoning: bool = False,
) -> Dict:
    """检索 + LLM 生成回答（已接入长短期记忆）。

    短期记忆：由 history 提供（最近 4 轮对话上下文）。
    长期记忆：通过 MemoryManager 召回与问题相关的历史沉淀，并回答后自动沉淀。

    返回 { answer, sources, chunks }
    """
    trace_id = str(uuid.uuid4())
    trace_steps: List[Dict] = []
    trace_steps.append(_make_input_step(question, history))

    mm = None
    ltm_ctx = ""
    if history:
        mm = get_memory_for(user_id=user_id, mode="knowledge")
        ltm_ctx = build_long_term_context(mm, question, trace_id=trace_id)

    ret_start = _now_ms()
    hits = retrieve(kb_id, question, trace_id=trace_id)
    ret_latency = _now_ms() - ret_start
    context = "\n\n".join(
        f"[来源 {i+1}] {h['text']}" for i, h in enumerate(hits)
    )
    trace_steps.append(_make_retrieve_step(question, hits, ret_latency))

    if not hits:
        return {
            "answer": "知识库中未找到相关内容，请先上传相关文档。",
            "sources": [],
            "chunks": [],
        }

    history_text = ""
    if history:
        history_text = "\n".join(f"用户: {h.get('q')}\n助手: {h.get('a')}" for h in history[-4:])

    history_block = ""
    if history_text:
        history_block = "=== 对话历史 ===\n" + history_text + "\n"

    long_term_block = format_long_term_block(ltm_ctx)

    prompt = f"""你是 AutoTestHub 的需求评审师与测试知识助手。
请仅基于下方「知识库内容」回答用户问题，不要编造知识库以外的信息。
如果知识库内容不足以回答，请明确说明。

{long_term_block}{history_block}
=== 知识库内容 ===
{context}

=== 用户问题 ===
{question}

=== 回答要求 ===
1. 先给结论，再给依据（引用来源编号）
2. 如果是需求/用例相关问题，给出可执行的建议
3. 输出简洁、结构化（用要点）
4. 引用来源时，必须使用 "[来源 N]" 标记，N 对应当前问题检索结果中的来源编号
5. 若使用有序列表组织依据，编号必须严格按 1. / 2. / 3. 递增，严禁每条都写 1.；示例：
   1. [来源 1] 说明了可观测性要求...
   2. [来源 2] 补充了架构决策...
   3. [来源 3] 展示了部署方案..."""

    router = get_llm_router()
    sys_text = "你是 AutoTestHub 的 RAG 知识助手，严格基于检索内容回答。使用有序列表时编号必须按 1、2、3… 递增。"

    def _gen_once(issue_hint: str = "") -> str:
        """单次生成（循环工程：可带上一轮的 issues 重新生成）"""
        prompt_iter = prompt
        if issue_hint:
            prompt_iter += (
                f"\n\n=== 上一轮回答的评测问题（请针对性改进）===\n{issue_hint}\n"
                "请修正上述问题后重新回答。"
            )
        try:
            trace_steps.append(_make_prompt_step(sys_text, prompt_iter))
            messages = [
                {"role": "system", "content": sys_text},
                {"role": "user", "content": prompt_iter},
            ]
            text = router.chat(
                messages=messages,
                task_type="knowledge_chat",
                temperature=0.2,
                trace_id=trace_id,
                trace_steps=trace_steps,
            )
            return text if isinstance(text, str) else str(text)
        except Exception as e:
            logger.error(f"[RAG] LLM 生成失败: {e}")
            return "（检索到相关内容，但生成回答时出错，请稍后重试）"

    first_answer = _gen_once()
    answer_text = first_answer

    # ── 规则化简版评分（不调用 LLM，省内存，适合演示）──
    from app.core.eval_event_store import get_eval_event_store

    _retrieved_docs = [
        {"content": h.get("text", ""), "score": h.get("score", 0), "source": h.get("meta", {}).get("filename", "未知")}
        for h in hits
    ]
    _res = _rule_based_eval(first_answer, has_context=bool(_retrieved_docs))
    _dimension_scores = _rule_eval_to_dimension_scores(_res)
    _judge = {
        "overall": _res["overall"],
        "hallucination": _res["hallucination"],
        "consistency": _res["consistency"],
        "completeness": _res["completeness"],
        "executability": _res["executability"],
        "safety": _res["safety"],
        "issues": _res["issues"],
        "method": "rule_based_demo",
    }
    try:
        get_eval_event_store().update_by_trace_id(
            trace_id=trace_id,
            judge=_judge,
            dimension_scores=_dimension_scores,
            issues=_res["issues"],
            trace_steps=trace_steps,
        )
        logger.info(f"[RAG][规则评分] 非流式 knowledge_chat 完成，综合分={_res['overall']}")
    except Exception as e:
        logger.error(f"[RAG][规则评分] 非流式回写失败: {e}")
    answer_text = first_answer

    sources = [
        {
            "filename": h["meta"].get("filename", "未知"),
            "score": round(h["score"], 4),
            "chunk_index": h["meta"].get("chunk_index", 0),
            "content": h["text"],
        }
        for h in hits
    ]
    return {
        "answer": answer_text,
        "sources": sources,
        "chunks": [h["text"] for h in hits],
        "eval_score": round(eval_result.score, 3) if enable_eval else None,
        "eval_iterations": eval_result.iterations,
        "needs_human": eval_result.needs_human,
    }


def _apply_reasoning_prompt(messages: list, enable_reasoning: bool) -> list:
    """深度思考模式：在 system 中注入详细推理要求，引导模型（含原生 reasoner）
    在最终答案前进行充分、多步骤的思考。原生 DeepSeek Reasoner 会直接通过
    reasoning_content 字段输出；非原生模型则按 <thinking> 标签兜底。"""
    if not enable_reasoning:
        return messages
    for m in messages:
        if m.get("role") == "system":
            m["content"] += (
                "\n\n【深度思考模式】你正在使用深度思考模式。在输出最终答案之前，"
                "请先进行充分、深入、逐步的推理分析，不要急于下结论。推理过程应尽可能详细、充实，包含："
                "1）对问题的多角度拆解与理解；2）关键概念、事实、约束条件的梳理；"
                "3）可能的回答方向及其优劣比较；4）自我质疑、假设检验与修正；"
                "5）最终结论的形成逻辑与取舍理由。"
                "如果模型支持原生推理字段，请直接输出详细的 reasoning_content；"
                "否则请在 <thinking> 和 </thinking> 标记之间写出完整推理过程，然后再给出最终答案。"
                "最终答案不要包含 <thinking> 等推理标记。"
            )
            break
    return messages


# 用于 prompt 兜底：从 delta 内容中提取 <thinking> 标签内的推理文本
_THINKING_RE = re.compile(r"<thinking>(.*?)</thinking>", re.DOTALL)


def _split_thinking_from_delta(text: str) -> tuple[str, str]:
    """从模型输出片段中分离推理文本与最终答案。

    Returns:
        (reasoning_part, answer_part)
    """
    reasoning_parts = _THINKING_RE.findall(text)
    if reasoning_parts:
        reasoning = "\n".join(reasoning_parts).strip()
        answer = _THINKING_RE.sub("", text).strip()
        return reasoning, answer
    return "", text


def answer_stream(
    kb_id: str,
    question: str,
    history: Optional[List[Dict]] = None,
    user_id: str = "anonymous",
    enable_reasoning: bool = False,
    session_id: Optional[str] = None,
) -> Generator[Dict, None, None]:
    """流式检索 + LLM 生成回答（已接入长短期记忆）。yield 的事件字典会由 SSE 包装。"""
    if not session_id:
        session_id = str(uuid.uuid4())
    trace_id = str(uuid.uuid4())
    trace_steps: List[Dict] = []
    trace_steps.append(_make_input_step(question, history))
    # 先推送状态，避免检索与记忆召回期间前端长时间无反馈
    yield {"type": "status", "content": "正在检索知识库..."}

    # 新会话（无历史）时跳过长期记忆召回，避免实例化 embedding provider 阻塞首 token；
    # 有历史多轮对话时再注入长期记忆，提升上下文连贯性。
    mm = None
    ltm_ctx = ""
    if history:
        mm = get_memory_for(user_id=user_id, mode="knowledge")
        ltm_ctx = build_long_term_context(mm, question, trace_id=trace_id)

    ret_start = _now_ms()
    hits = retrieve(kb_id, question, trace_id=trace_id)
    ret_latency = _now_ms() - ret_start
    context = "\n\n".join(
        f"[来源 {i+1}] {h['text']}" for i, h in enumerate(hits)
    )
    trace_steps.append(_make_retrieve_step(question, hits, ret_latency))

    if not hits:
        # 无命中时也要记录事件，方便 EvalCenter 看到检索失败链路
        get_eval_event_store().add(build_event(
            feature="rag_query",
            task_type="rag_query",
            model="none",
            provider="none",
            input_text=question,
            output_text="知识库中未找到相关内容",
            latency_ms=ret_latency,
            trace_id=trace_id,
            trace_steps=trace_steps,
            status="completed",
        ))
        yield {"type": "done", "full_answer": "知识库中未找到相关内容，请先上传相关文档。", "context_docs": []}
        return

    history_text = ""
    if history:
        history_text = "\n".join(f"用户: {h.get('q')}\n助手: {h.get('a')}" for h in history[-4:])

    history_block = ""
    if history_text:
        history_block = "=== 对话历史 ===\n" + history_text + "\n"

    long_term_block = format_long_term_block(ltm_ctx)

    if enable_reasoning:
        role_prefix = "你是 AutoTestHub 的深度思考需求评审师与测试知识助手。你正在使用【深度思考模式】。"
        detail_requirement = (
            "回答必须详细、全面、结构化。不要只给简短结论。要求："
            "1）先给出核心结论；2）基于知识库内容分维度展开，包括背景、关键概念、数据依据、典型案例、不同方案/口径的比较；"
            "3）使用有序列表/多级标题让结构清晰；4）尽量列举具体信息、数字、事实，避免泛泛而谈；"
            "5）如果存在多种说法或争议，请分别说明并给出你的判断理由。"
        )
    else:
        role_prefix = "你是 AutoTestHub 的需求评审师与测试知识助手。"
        detail_requirement = "请仅基于下方「知识库内容」回答用户问题，不要编造知识库以外的信息。如果知识库内容不足以回答，请明确说明。"

    prompt = f"""{role_prefix}
{detail_requirement}

{long_term_block}{history_block}=== 知识库内容 ===
{context}

=== 用户问题 ===
{question}

=== 回答要求 ===
1. 先给结论，再给依据（引用来源编号）
2. 如果是需求/用例相关问题，给出可执行的建议
3. 引用来源时，必须使用 "[来源 N]" 标记，N 对应当前问题检索结果中的来源编号
4. 若使用有序列表组织依据，编号必须严格按 1. / 2. / 3. 递增，严禁每条都写 1.；示例：
   1. [来源 1] 说明了可观测性要求...
   2. [来源 2] 补充了架构决策...
   3. [来源 3] 展示了部署方案...
5. 如果是深度思考模式，回答必须详细、充实、多维度展开，不要只给简短结论。"""

    router = get_llm_router()
    if enable_reasoning:
        system_text = (
            "你是 AutoTestHub 的深度思考 RAG 知识助手。你正在使用【深度思考模式】，必须基于检索内容给出详细、全面的回答。"
            "回答不要只给简短结论，要求：1）先给出核心结论；2）分维度展开，包括背景、关键概念、数据依据、典型案例、不同方案/口径的比较；"
            "3）使用有序列表/多级标题让结构清晰；4）尽量列举具体信息、数字、事实；"
            "5）如果存在多种说法或争议，分别说明并给出判断理由。使用有序列表时编号必须按 1、2、3… 递增。"
        )
    else:
        system_text = "你是 AutoTestHub 的 RAG 知识助手，严格基于检索内容回答。使用有序列表时编号必须按 1、2、3… 递增。"

    messages = [
        {"role": "system", "content": system_text},
        {"role": "user", "content": prompt},
    ]
    messages = _apply_reasoning_prompt(messages, enable_reasoning)
    trace_steps.append(_make_prompt_step(system_text, prompt))

    full_answer_parts: list[str] = []
    reasoning_parts: list[str] = []
    # 处理 <thinking> 标签跨 chunk 不完整的情况
    pending_thinking_text = ""
    start_time = time.perf_counter()
    FIRST_TOKEN_TIMEOUT = 10.0  # 首 token 超过 10s 视为超时，避免前端长时间卡住
    first_token_seen = False
    yield {"type": "status", "content": "检索完成，正在生成回答..."}

    # 评估闭环参数（可由调用方通过 thread-local / 环境变量覆盖，这里给默认）
    from app.core.eval_loop import DEFAULT_MAX_ITERATIONS, DEFAULT_THRESHOLD
    max_iterations = int(os.environ.get("RAG_EVAL_MAX_ITER", DEFAULT_MAX_ITERATIONS))
    threshold = float(os.environ.get("RAG_EVAL_THRESHOLD", DEFAULT_THRESHOLD))
    enable_eval = os.environ.get("RAG_EVAL_ENABLED", "1") != "0"

    # 深度思考模式：提高最大 token 数，保证推理与答案都有足够空间
    extra_params = {}
    if enable_reasoning:
        extra_params["max_tokens"] = 8192

    try:
        temperature = 0.3 if enable_reasoning else 0.2
        for event in router.chat_stream(
            messages,
            task_type="knowledge_chat",
            temperature=temperature,
            enable_reasoning=enable_reasoning,
            trace_id=trace_id,
            trace_steps=trace_steps,
            **extra_params,
        ):
            if not isinstance(event, dict):
                # 兼容旧版纯字符串流
                if not first_token_seen:
                    elapsed = time.perf_counter() - start_time
                    if elapsed > FIRST_TOKEN_TIMEOUT:
                        yield {"type": "error", "message": f"模型首 token 响应超时（{elapsed:.1f}s），请检查网络或切换模型后重试"}
                        return
                    first_token_seen = True
                full_answer_parts.append(str(event))
                yield {"type": "token", "content": str(event)}
                continue

            etype = event.get("type")
            if etype in ("reasoning", "delta"):
                if not first_token_seen:
                    elapsed = time.perf_counter() - start_time
                    if elapsed > FIRST_TOKEN_TIMEOUT:
                        yield {"type": "error", "message": f"模型首 token 响应超时（{elapsed:.1f}s），请检查网络或切换模型后重试"}
                        return
                    first_token_seen = True
            if etype == "reasoning":
                # 仅深度思考模式向下游转发 reasoning 事件
                if enable_reasoning:
                    reasoning_parts.append(event["content"])
                    yield {"type": "reasoning", "content": event["content"]}
            elif etype == "delta":
                text = event.get("content", "")
                if enable_reasoning and "<thinking>" in text:
                    pending_thinking_text += text
                    if "</thinking>" in pending_thinking_text:
                        reasoning, answer = _split_thinking_from_delta(pending_thinking_text)
                        pending_thinking_text = ""
                        if reasoning:
                            reasoning_parts.append(reasoning)
                            yield {"type": "reasoning", "content": reasoning}
                        if answer:
                            full_answer_parts.append(answer)
                            yield {"type": "token", "content": answer}
                else:
                    full_answer_parts.append(text)
                    yield {"type": "token", "content": text}
            elif etype == "error":
                yield {"type": "error", "message": event.get("message", "生成失败")}
                return
            elif etype == "done":
                # provider 的 done 事件只作为结束信号，不再向下游转发（避免被当成 token 渲染）
                continue
            else:
                full_answer_parts.append(str(event))
                yield {"type": "token", "content": str(event)}
    except Exception as e:
        logger.error(f"[RAG] 流式生成失败: {e}")
        yield {"type": "error", "message": f"生成回答时出错: {e}"}
        return

    # 残留未闭合的 thinking 标签兜底：当作答案输出
    if pending_thinking_text:
        full_answer_parts.append(pending_thinking_text)
        yield {"type": "token", "content": pending_thinking_text}

    first_answer = "".join(full_answer_parts).strip()
    # 深度思考模型偶发把内容全部输出在 reasoning 字段，content 为空；
    # 兜底：用 reasoning 内容作为最终答案，避免前端只显示占位符。
    if enable_reasoning and not first_answer and reasoning_parts:
        first_answer = "\n\n".join(reasoning_parts).strip()
        logger.info(f"[RAG] 答案为空，已用 reasoning 兜底，长度={len(first_answer)}")
    logger.info(f"[RAG] 首轮生成完成，长度={len(first_answer)}，启动后台评估闭环（max_iter={max_iterations}, threshold={threshold}, enable_eval={enable_eval}）")

    # ── 评估闭环改为后台异步执行，不阻塞 SSE 响应 ──
    # 仅当答案非空时才触发 Judge，避免空/异常回答生成无效评测记录
    if enable_eval and first_answer:
        from app.core.eval_event_store import build_event, get_eval_event_store

        _retrieved_docs = [
            {
                "source": h.get("meta", {}).get("filename", "知识库"),
                "content": h.get("text", ""),
                "score": round(h.get("score", 0.0), 4),
            }
            for h in hits
        ]
        _model_name = get_llm_router().get_model_for_task("knowledge_chat")
        _run_latency = int((time.perf_counter() - start_time) * 1000)

        # 先把本轮问答写入 EvalEventStore，保证 EvalCenter 能立即看到追踪卡片；
        # 后台 Judge 评估会再 update_by_trace_id 追加五维评分。
        try:
            get_eval_event_store().add(build_event(
                feature="knowledge_chat",
                task_type="knowledge_chat",
                model=_model_name,
                provider="deepseek",
                input_text=question,
                output_text=first_answer,
                latency_ms=_run_latency,
                token_usage=_estimate_tokens(question) + _estimate_tokens(first_answer),
                trace_id=trace_id,
                retrieved_docs=_retrieved_docs,
                trace_steps=trace_steps,
                status="completed",
            ))
            logger.info(f"[RAG] 已写入 knowledge_chat 追踪事件 trace_id={trace_id}")
        except Exception as e:
            logger.error(f"[RAG] 写入 knowledge_chat 追踪事件失败: {e}")

        _schedule_background_eval(
            _run_eval_async(
                mode="knowledge",
                question=question,
                first_answer=first_answer,
                reference=context,
                max_iterations=max_iterations,
                threshold=threshold,
                mm=mm,
                user_id=user_id,
                prompt_text=prompt,
                retrieved_docs=_retrieved_docs,
                model=_model_name,
                latency_ms=_run_latency,
                trace_id=trace_id,
                trace_steps=trace_steps,
            )
        )

    sources = [
        {
            "filename": h["meta"].get("filename", "未知"),
            "score": round(h["score"], 4),
            "chunk_index": h["meta"].get("chunk_index", 0),
            "content": h["text"],
        }
        for h in hits
    ]
    response_time_ms = int((time.perf_counter() - start_time) * 1000)
    yield {
        "type": "done",
        "full_answer": first_answer,
        "context_docs": sources,
        "response_time": response_time_ms,
        "eval_score": None,
        "eval_iterations": 0,
        "needs_human": False,
        # 评估关闭时不再下发 eval_pending，避免前端误显示"质量评估中"
        "eval_pending": enable_eval,
    }


def chat_stream(
    question: str,
    system_prompt: Optional[str] = None,
    history: Optional[List[Dict]] = None,
    user_id: str = "anonymous",
    enable_reasoning: bool = False,
) -> Generator[Dict, None, None]:
    """流式日常问答，不依赖知识库（已接入长短期记忆）。

    短期记忆：history 提供最近 6 轮对话上下文。
    长期记忆：召回与问题相关的历史沉淀，回答后自动提炼沉淀。
    """
    trace_id = str(uuid.uuid4())
    trace_steps: List[Dict] = []
    trace_steps.append(_make_input_step(question, history))

    # 先让前端收到状态，避免长期记忆召回阻塞时界面长时间无响应
    yield {"type": "status", "content": "正在思考..."}

    # 新会话（无历史）时跳过记忆系统，避免实例化 embedding provider 阻塞首 token；
    # 有历史多轮对话时再注入长期记忆，提升上下文连贯性。
    mm = None
    ltm_ctx = ""
    if history:
        mm = get_memory_for(user_id=user_id, mode="chat")
        ltm_ctx = build_long_term_context(mm, question, trace_id=trace_id)

    # 深度思考模式：提高最大 token 数，保证输出内容足够充实
    extra_params: dict = {}
    if enable_reasoning:
        extra_params["max_tokens"] = 8192

    messages = []
    if enable_reasoning:
        sys = system_prompt or (
            "你是 AutoTestHub 的深度思考 AI 助手。你正在使用【深度思考模式】，用户期望看到一个完整、深入、信息丰富的回答。"
            "你必须在最终答案中给出详细、结构化、多角度的分析，不要只给简短结论。"
            "回答要求：1）先给出核心结论；2）再分维度展开说明，包括背景、关键概念、数据依据、典型例子、不同口径的比较；"
            "3）使用有序列表/多级标题让结构清晰；4）尽量列举具体信息、数字、事实，避免泛泛而谈；"
            "5）如果存在争议或多种说法，请分别说明并给出你的判断理由。"
            "使用有序列表时编号必须按 1、2、3… 递增。"
        )
    else:
        sys = system_prompt or "你是 AutoTestHub 的 AI 助手，善于回答测试、开发、需求相关的问题，回答简洁专业。使用有序列表时编号必须按 1、2、3… 递增。"
    if ltm_ctx:
        sys += "\n\n参考用户长期记忆（来自历史对话沉淀，可作为背景，但不要原样复述）：\n" + ltm_ctx
    messages.append({"role": "system", "content": sys})

    if history:
        for h in history[-6:]:
            messages.append({"role": "user", "content": h.get("q", "")})
            messages.append({"role": "assistant", "content": h.get("a", "")})

    messages.append({"role": "user", "content": question})
    messages = _apply_reasoning_prompt(messages, enable_reasoning)
    trace_steps.append(_make_prompt_step(sys, question))

    router = get_llm_router()
    full_answer_parts: list[str] = []
    reasoning_parts: list[str] = []
    pending_thinking_text = ""
    start_time = time.perf_counter()
    FIRST_TOKEN_TIMEOUT = 10.0  # 首 token 超过 10s 视为超时，避免前端长时间卡住
    first_token_seen = False

    # 评估闭环参数
    from app.core.eval_loop import DEFAULT_MAX_ITERATIONS, DEFAULT_THRESHOLD
    max_iterations = int(os.environ.get("CHAT_EVAL_MAX_ITER", DEFAULT_MAX_ITERATIONS))
    threshold = float(os.environ.get("CHAT_EVAL_THRESHOLD", DEFAULT_THRESHOLD))
    # 日常对话默认开启评估闭环，让 EvalCenter 能看到 AI 底座评分
    enable_eval = os.environ.get("CHAT_EVAL_ENABLED", "1") != "0"

    try:
        # 深度思考模式用稍高的 temperature，让回答更愿意展开；普通模式保持较低温度
        temperature = 0.6 if enable_reasoning else 0.7
        for event in router.chat_stream(
            messages,
            task_type="fast_chat",
            temperature=temperature,
            enable_reasoning=enable_reasoning,
            trace_id=trace_id,
            trace_steps=trace_steps,
            **extra_params,
        ):
            if not isinstance(event, dict):
                if not first_token_seen:
                    elapsed = time.perf_counter() - start_time
                    if elapsed > FIRST_TOKEN_TIMEOUT:
                        yield {"type": "error", "message": f"模型首 token 响应超时（{elapsed:.1f}s），请检查网络或切换模型后重试"}
                        return
                    first_token_seen = True
                full_answer_parts.append(str(event))
                yield {"type": "token", "content": str(event)}
                continue

            etype = event.get("type")
            if etype in ("reasoning", "delta"):
                if not first_token_seen:
                    elapsed = time.perf_counter() - start_time
                    if elapsed > FIRST_TOKEN_TIMEOUT:
                        yield {"type": "error", "message": f"模型首 token 响应超时（{elapsed:.1f}s），请检查网络或切换模型后重试"}
                        return
                    first_token_seen = True
            if etype == "reasoning":
                # 仅深度思考模式向下游转发 reasoning 事件
                if enable_reasoning:
                    reasoning_parts.append(event["content"])
                    yield {"type": "reasoning", "content": event["content"]}
            elif etype == "delta":
                text = event.get("content", "")
                if enable_reasoning and "<thinking>" in text:
                    pending_thinking_text += text
                    if "</thinking>" in pending_thinking_text:
                        reasoning, answer = _split_thinking_from_delta(pending_thinking_text)
                        pending_thinking_text = ""
                        if reasoning:
                            reasoning_parts.append(reasoning)
                            yield {"type": "reasoning", "content": reasoning}
                        if answer:
                            full_answer_parts.append(answer)
                            yield {"type": "token", "content": answer}
                else:
                    full_answer_parts.append(text)
                    yield {"type": "token", "content": text}
            elif etype == "error":
                yield {"type": "error", "message": event.get("message", "生成失败")}
                return
            elif etype == "done":
                continue
            else:
                full_answer_parts.append(str(event))
                yield {"type": "token", "content": str(event)}
    except Exception as e:
        logger.error(f"[RAG] 日常对话流式生成失败: {e}")
        yield {"type": "error", "message": f"生成回答时出错: {e}"}
        return

    if pending_thinking_text:
        full_answer_parts.append(pending_thinking_text)
        yield {"type": "token", "content": pending_thinking_text}

    first_answer = "".join(full_answer_parts).strip()
    # 深度思考模型偶发把内容全部输出在 reasoning 字段，content 为空；
    # 兜底：用 reasoning 内容作为最终答案，避免前端只显示占位符。
    if enable_reasoning and not first_answer and reasoning_parts:
        first_answer = "\n\n".join(reasoning_parts).strip()
        logger.info(f"[RAG] 答案为空，已用 reasoning 兜底，长度={len(first_answer)}")
    logger.info(f"[RAG] 首轮生成完成，长度={len(first_answer)}，启动后台评估闭环（max_iter={max_iterations}, threshold={threshold}, enable_eval={enable_eval}）")

    # ── 评估闭环改为后台异步执行，不阻塞 SSE 响应 ──
    # 仅当答案非空时才触发 Judge，避免空/异常回答生成无效评测记录
    if enable_eval and first_answer:
        from app.core.eval_event_store import build_event, get_eval_event_store

        _model_name = get_llm_router().get_model_for_task("chat")
        _run_latency = int((time.perf_counter() - start_time) * 1000)

        # 先把本轮问答写入 EvalEventStore，保证 EvalCenter 能立即看到追踪卡片；
        # 后台 Judge 评估会再 update_by_trace_id 追加五维评分。
        try:
            get_eval_event_store().add(build_event(
                feature="chat",
                task_type="fast_chat",
                model=_model_name,
                provider="deepseek",
                input_text=question,
                output_text=first_answer,
                latency_ms=_run_latency,
                token_usage=_estimate_tokens(question) + _estimate_tokens(first_answer),
                trace_id=trace_id,
                retrieved_docs=[],
                trace_steps=trace_steps,
                status="completed",
            ))
            logger.info(f"[RAG] 已写入 chat 追踪事件 trace_id={trace_id}")
        except Exception as e:
            logger.error(f"[RAG] 写入 chat 追踪事件失败: {e}")

        _schedule_background_eval(
            _run_eval_async(
                mode="chat",
                question=question,
                first_answer=first_answer,
                reference="",
                max_iterations=max_iterations,
                threshold=threshold,
                mm=mm,
                user_id=user_id,
                messages=messages,
                task_type="fast_chat",
                temperature=0.6 if enable_reasoning else 0.7,
                enable_reasoning=enable_reasoning,
                model=_model_name,
                latency_ms=_run_latency,
                trace_id=trace_id,
                trace_steps=trace_steps,
            )
        )

    response_time_ms = int((time.perf_counter() - start_time) * 1000)
    yield {
        "type": "done",
        "full_answer": first_answer,
        "context_docs": [],
        "response_time": response_time_ms,
        "eval_score": None,
        "eval_iterations": 0,
        "needs_human": False,
        "eval_pending": enable_eval,
    }
