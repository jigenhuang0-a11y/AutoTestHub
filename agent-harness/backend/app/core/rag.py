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
):
    """
    后台异步执行评估闭环：评分 -> 不达标重生成 -> 通过则沉淀记忆 -> 未通过转人工协同。
    不阻塞前端 SSE 流式响应。
    """
    from app.core.eval_loop import _make_evaluator, TESTING_CRITERIA, _run_judge_and_persist

    scorer = _make_evaluator(TESTING_CRITERIA)
    candidates = [first_answer]
    best_answer = first_answer
    best_score = -1.0
    import uuid as _uuid
    trace_id = str(_uuid.uuid4())
    best_issues: List[str] = []

    router = get_llm_router()

    for iteration in range(1, max_iterations + 1):
        answer = candidates[iteration - 1]
        ev = await asyncio.to_thread(scorer, answer, reference)
        score = float(ev.get("score", 0.0))
        issues = ev.get("issues", []) or []
        if score > best_score:
            best_score, best_answer, best_issues = score, answer, issues
        logger.info(f"[RAG][后台评估] {mode} 第 {iteration}/{max_iterations} 轮 score={score:.2f}")
        if score >= threshold:
            try:
                sink_memory(mm, question, best_answer, llm_fn=_llm_fn_for_memory)
                logger.info(f"[RAG][后台评估] {mode} 评估通过，已沉淀长期记忆")
            except Exception as e:
                logger.error(f"[RAG][后台评估] 沉淀记忆失败: {e}")
            # 通过即退出循环，对最终答案做五维 Judge 并写入评估中心（供全链路评测看板）
            _run_judge_and_persist(
                result=None, question=question, answer=best_answer, reference=reference,
                feature="knowledge_chat" if mode == "knowledge" else "chat",
                trace_id=trace_id, user_id=user_id,
                retrieved_docs=retrieved_docs, model=model, latency_ms=latency_ms,
            )
            return
        if iteration < max_iterations:
            issue_hint = "\n".join(f"- {i}" for i in issues) if issues else ""
            if mode == "chat":
                new_answer = await _gen_once_async(
                    router, messages or [], task_type, temperature,
                    issue_hint=f"上一轮回答的评测问题如下，请针对性改进后重新回答：\n{issue_hint}",
                    enable_reasoning=enable_reasoning,
                )
            else:  # knowledge
                new_answer = await _gen_once_async(
                    router,
                    [
                        {"role": "system", "content": "你是 AutoTestHub 的 RAG 知识助手，严格基于检索内容回答。使用有序列表时编号必须按 1、2、3… 递增。"},
                        {"role": "user", "content": prompt_text + (f"\n\n=== 上一轮回答的评测问题（请针对性改进）===\n{issue_hint}\n请修正上述问题后重新回答。" if issue_hint else "")},
                    ],
                    task_type="rag_query",
                    temperature=0.2,
                )
            if new_answer:
                candidates.append(new_answer)
            else:
                break

    # 循环耗尽仍未达标
    logger.warning(f"[RAG][后台评估] {mode} 循环耗尽仍未达标，score={best_score:.2f}，转人工协同")
    # 不论达标与否，都对最终答案做五维 Judge 并写入评估中心（供全链路评测看板）
    _run_judge_and_persist(
        result=None, question=question, answer=best_answer, reference=reference,
        feature="knowledge_chat" if mode == "knowledge" else "chat",
        trace_id=trace_id, user_id=user_id,
        retrieved_docs=retrieved_docs, model=model, latency_ms=latency_ms,
    )
    try:
        notify_human_review(
            question=question,
            best_answer=best_answer,
            score=best_score,
            issues=best_issues,
            iterations=max_iterations,
            ctx={"mode": mode, "user_id": user_id},
            criteria=TESTING_CRITERIA,
        )
    except Exception as e:
        logger.error(f"[RAG][后台评估] 人工协同通知失败: {e}")


def _schedule_background_eval(coro):
    """把后台评估协程投到主事件循环，失败则静默丢弃（不阻塞响应）。"""
    if _MAIN_LOOP and not _MAIN_LOOP.is_closed():
        try:
            asyncio.run_coroutine_threadsafe(coro, _MAIN_LOOP)
            return
        except Exception as e:
            logger.warning(f"[RAG] 后台评估调度失败: {e}")
    logger.warning("[RAG] 无可用事件循环，后台评估未启动")


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


def retrieve(kb_id: str, question: str, top_k: int = TOP_K) -> List[Dict]:
    """检索相关 chunk（跨多个文档）。embedding 失败时降级返回空列表，避免请求挂死。"""
    try:
        provider = get_embedding_provider()
        store = get_vector_store(f"kb_{kb_id}", dim=provider.dim)
        q_vec = provider.embed([question])[0]
        return store.search(q_vec, top_k=top_k)
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
    mm = None
    ltm_ctx = ""
    if history:
        mm = get_memory_for(user_id=user_id, mode="knowledge")
        ltm_ctx = build_long_term_context(mm, question)

    hits = retrieve(kb_id, question)
    context = "\n\n".join(
        f"[来源 {i+1}] {h['text']}" for i, h in enumerate(hits)
    )

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

    def _gen_once(issue_hint: str = "") -> str:
        """单次生成（循环工程：可带上一轮的 issues 重新生成）"""
        prompt_iter = prompt
        if issue_hint:
            prompt_iter += (
                f"\n\n=== 上一轮回答的评测问题（请针对性改进）===\n{issue_hint}\n"
                "请修正上述问题后重新回答。"
            )
        try:
            text = router.execute(
                task_type="rag_query",
                prompt=prompt_iter,
                system_prompt="你是 AutoTestHub 的 RAG 知识助手，严格基于检索内容回答。使用有序列表时编号必须按 1、2、3… 递增。",
                temperature=0.2,
            )
            return text if isinstance(text, str) else str(text)
        except Exception as e:
            logger.error(f"[RAG] LLM 生成失败: {e}")
            return "（检索到相关内容，但生成回答时出错，请稍后重试）"

    first_answer = _gen_once()
    answer_text = first_answer

    # ── 评估闭环（循环工程 + 人工协同）──
    from app.core.eval_loop import run_eval_loop, DEFAULT_MAX_ITERATIONS, DEFAULT_THRESHOLD
    max_iterations = int(os.environ.get("RAG_EVAL_MAX_ITER", DEFAULT_MAX_ITERATIONS))
    threshold = float(os.environ.get("RAG_EVAL_THRESHOLD", DEFAULT_THRESHOLD))
    enable_eval = os.environ.get("RAG_EVAL_ENABLED", "1") != "0"

    def _regenerate(issues: list) -> str:
        issue_hint = "\n".join(f"- {i}" for i in issues) if issues else ""
        logger.info(f"[RAG] 评估未达标（非流式），触发重生成（最多 {max_iterations} 轮）")
        return _gen_once(issue_hint)

    eval_result = run_eval_loop(
        question=question,
        candidates=[first_answer],
        reference=context,
        max_iterations=max_iterations,
        threshold=threshold,
        enable_eval=enable_eval,
        regenerate_fn=_regenerate,
        sink_if_passed=lambda ans: sink_memory(mm, question, ans, llm_fn=_llm_fn_for_memory),
        human_review_ctx={"mode": "knowledge", "user_id": user_id},
        feature="knowledge_chat",
        user_id=user_id,
        session_id=session_id,
        trace_id=trace_id,
    )
    answer_text = eval_result.final_answer or first_answer

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
    import uuid as _uuid
    if not session_id:
        session_id = str(_uuid.uuid4())
    trace_id = str(_uuid.uuid4())
    # 先推送状态，避免检索与记忆召回期间前端长时间无反馈
    yield {"type": "status", "content": "正在检索知识库..."}

    # 新会话（无历史）时跳过长期记忆召回，避免实例化 embedding provider 阻塞首 token；
    # 有历史多轮对话时再注入长期记忆，提升上下文连贯性。
    mm = None
    ltm_ctx = ""
    if history:
        mm = get_memory_for(user_id=user_id, mode="knowledge")
        ltm_ctx = build_long_term_context(mm, question)

    hits = retrieve(kb_id, question)
    context = "\n\n".join(
        f"[来源 {i+1}] {h['text']}" for i, h in enumerate(hits)
    )

    if not hits:
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
        for event in router.chat_stream(messages, task_type="rag_query", temperature=temperature, enable_reasoning=enable_reasoning, **extra_params):
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
        _retrieved_docs = [
            {
                "source": h.get("meta", {}).get("filename", "知识库"),
                "content": h.get("text", ""),
                "score": round(h.get("score", 0.0), 4),
            }
            for h in hits
        ]
        _model_name = (get_llm_router().default_model if hasattr(get_llm_router(), "default_model") else None)
        _run_latency = int((time.perf_counter() - start_time) * 1000)
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
    # 先让前端收到状态，避免长期记忆召回阻塞时界面长时间无响应
    yield {"type": "status", "content": "正在思考..."}

    # 新会话（无历史）时跳过记忆系统，避免实例化 embedding provider 阻塞首 token；
    # 有历史多轮对话时再注入长期记忆，提升上下文连贯性。
    mm = None
    ltm_ctx = ""
    if history:
        mm = get_memory_for(user_id=user_id, mode="chat")
        ltm_ctx = build_long_term_context(mm, question)

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
    # 日常对话默认关闭评估闭环：避免每次问答都显示"质量评估中"并推送飞书
    enable_eval = os.environ.get("CHAT_EVAL_ENABLED", "0") != "0"

    try:
        # 深度思考模式用稍高的 temperature，让回答更愿意展开；普通模式保持较低温度
        temperature = 0.6 if enable_reasoning else 0.7
        for event in router.chat_stream(messages, task_type="fast_chat", temperature=temperature, enable_reasoning=enable_reasoning, **extra_params):
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
        _model_name = (get_llm_router().default_model if hasattr(get_llm_router(), "default_model") else None)
        _run_latency = int((time.perf_counter() - start_time) * 1000)
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
