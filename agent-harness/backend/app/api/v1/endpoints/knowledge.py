"""
知识中枢（RAG）API — 核心卖点

提供（路径与前端 knowledgeBaseAPI 对齐，前端无需改动）：
  - GET    /knowledge/knowledge-bases/            列出知识库
  - POST   /knowledge/knowledge-bases/            创建知识库
  - GET    /knowledge/knowledge-bases/{id}/       获取详情
  - DELETE /knowledge/knowledge-bases/{id}/       删除知识库
  - POST   /knowledge/knowledge-bases/{id}/upload_document/   上传文档（txt/md）
  - POST   /knowledge/knowledge-bases/{id}/ask/               问答（检索 + LLM）
  - GET    /knowledge/knowledge-bases/{id}/chat_history/      会话历史（占位返回空）

AI 底座集成：
  - embedding.py 提供向量化（DashScope / 本地兜底）
  - vector_store.py 提供本地向量存储（接口对齐 Milvus）
  - rag.py 编排切分/检索/生成
  - 可被 Supervisor 编排层作为 `knowledge` worker 调度
"""
from __future__ import annotations

import logging
import os
import uuid
import threading
import time
from io import BytesIO

import json
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.api.v1.endpoints.auth import get_current_user, require_non_viewer
from app.core.task_store import TaskStore, get_task_store
from app.core import rag
from app.core.router import LLMRouter

# PDF / Word 解析依赖为可选；未安装时提示用户安装，避免服务起不来
_PDF_AVAILABLE = False
try:
    import pdfplumber
    _PDF_AVAILABLE = True
except ImportError:
    pdfplumber = None

_DOCX_AVAILABLE = False
try:
    import docx
    _DOCX_AVAILABLE = True
except ImportError:
    docx = None
from app.core.vector_store import get_vector_store

logger = logging.getLogger(__name__)


def _generate_title(question: str) -> str:
    """用 LLM 为会话生成不超过 8 个字的标题；失败则截前 8 字"""
    try:
        router = LLMRouter()
        messages = [
            {
                "role": "system",
                "content": "你是一名标题生成助手。请根据用户问题生成一个简洁标题，不超过 8 个汉字，不要标点、不要解释，只返回标题本身。",
            },
            {"role": "user", "content": f"问题：{question}\n标题："},
        ]
        title = router.chat(messages, task_type="fast_chat").strip()
        # 清理标点与空格
        title = title.replace("\n", "").replace("\r", "").strip("\"'“”【】[]")
        if title:
            # 按字节/字符截断到 8 个字符以内
            return title[:8]
    except Exception as e:
        logger.warning(f"[KB] 生成会话标题失败: {e}")
    # 兜底：取问题前 8 字
    return question.strip()[:8]


def _save_chat_round(
    store: TaskStore,
    user_id: str,
    question: str,
    answer: str,
    mode: str,
    session_id: Optional[str] = None,
    kb_id: Optional[str] = None,
    eval_score: float = None,
    needs_human: bool = False,
) -> str:
    """保存一轮问答到会话；返回 session_id"""
    # 无论是预生成的新 session_id 还是已有会话，都先 UPSERT 会话元数据，
    # 防止预生成 id 时 chat_sessions 表没有对应记录导致左侧列表为空。
    sid = session_id or str(uuid.uuid4())
    store.save_chat_session(
        user_id=user_id,
        title=_generate_title(question),
        mode=mode,
        kb_id=kb_id,
        session_id=sid,
    )
    store.save_chat_message(sid, "user", question)
    store.save_chat_message(sid, "assistant", answer, eval_score=eval_score, needs_human=needs_human)
    return sid


def _extract_pdf_text(stream: BytesIO) -> str:
    """从 PDF 文件流中提取文本。"""
    texts = []
    with pdfplumber.open(stream) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                texts.append(page_text)
    return "\n".join(texts)


def _extract_docx_text(stream: BytesIO) -> str:
    """从 Word 文件流中提取文本。"""
    document = docx.Document(stream)
    return "\n".join(p.text for p in document.paragraphs if p.text)


router = APIRouter(tags=["knowledge-rag"])


# ─────────────────────────────────────────────────────────────────────────────
# 后台生成任务管理：把 LLM 生成放到独立线程，结果写入内存缓存；
# 前端（多个标签页 / 切换页面后重连）都作为「消费者」从缓存拉增量。
# 这样即使某个 SSE 连接断开，生成任务仍在后台继续跑，不会中断。
# ─────────────────────────────────────────────────────────────────────────────
class _GenTask:
    def __init__(self):
        self.events = []          # 按序累积的所有 SSE 事件
        self.full_answer = ''     # 累积的完整答案（delta 事件拼接），供前端脱离 SSE 查询结果
        self.done = False
        self.error = None
        self.lock = threading.Lock()
        # 持久化所需元数据（在 SSE 消费者线程里写库，避免后台线程直接碰 DB）
        self.session_id = ''
        self.question = ''
        self.mode = 'knowledge'
        self.kb_id = None
        self.user_id = ''
        self.saved = False  # 是否已落库，保证只保存一次


GEN_TASKS: dict[str, _GenTask] = {}
GEN_TASKS_CLEANUP_AFTER = 3600  # 任务完成后 1 小时清理


def _run_gen_task(task_id: str, gen_callable, on_done=None):
    """在线程中迭代同步生成器，把事件写入 GEN_TASKS[task_id]，结束后调用 on_done。"""
    task = GEN_TASKS.get(task_id)
    if task is None:
        return
    try:
        for event in gen_callable():
            with task.lock:
                task.events.append(event)
                # 累积完整答案，供前端通过 result 接口脱离 SSE 查询最终结果
                if event.get("type") == "delta":
                    task.full_answer += event.get("content", "")
        with task.lock:
            task.done = True
    except Exception as e:  # noqa: BLE001
        logger.error(f"[GenTask] {task_id} 生成失败: {e}")
        with task.lock:
            task.error = str(e)
            task.done = True
    finally:
        if on_done:
            try:
                on_done()
            except Exception as e:  # noqa: BLE001
                logger.warning(f"[GenTask] {task_id} on_done 失败: {e}")


def _consume_generator(task_id: str, offset: int = 0):
    """消费者生成器：从 offset 开始把 GEN_TASKS[task_id] 的增量事件推给 SSE。"""
    task = GEN_TASKS.get(task_id)
    if task is None:
        yield _sse_event({"type": "error", "message": "任务不存在或已过期"})
        return
    idx = max(0, min(offset, len(task.events)))
    while True:
        with task.lock:
            new_events = task.events[idx:]
            done = task.done
            error = task.error
        for ev in new_events:
            yield _sse_event(ev)
            idx += 1
        if done:
            if error:
                yield _sse_event({"type": "error", "message": error})
            # 任务结束：在 SSE 请求线程里把完整结果落库（仅一次，且处于请求线程，DB 线程安全）
            try:
                with task.lock:
                    if not task.saved:
                        task.saved = True
                        full = []
                        for ev in task.events:
                            if ev.get("type") == "delta":
                                full.append(ev.get("content", ""))
                            elif ev.get("type") == "token":
                                full.append(ev.get("content", ""))
                        full_answer = "".join(full)
                        eval_score = None
                        needs_human = False
                        for ev in task.events:
                            if ev.get("type") == "done":
                                eval_score = ev.get("eval_score")
                                needs_human = bool(ev.get("needs_human"))
                        if full_answer:
                            _save_chat_round(
                                store=get_task_store(),
                                user_id=task.user_id,
                                question=task.question,
                                answer=full_answer,
                                mode=task.mode,
                                session_id=task.session_id,
                                kb_id=task.kb_id,
                                eval_score=eval_score,
                                needs_human=needs_human,
                            )
            except Exception as e:  # noqa: BLE001
                logger.warning(f"[GenTask] {task_id} 落库失败: {e}")
            yield _sse_event("[DONE]")
            return
        # 无新事件时短暂等待，避免空轮询
        time.sleep(0.1)


def _start_gen_task(kb_id: Optional[str], body: "KBQuery", user_id: str, mode: str):
    """
    创建后台生成任务，立即返回 (task_id, session_id)。
    SSE 流由调用方通过 _consume_generator(task_id) 消费；
    任务本身在独立线程跑，不依赖 HTTP 连接生命周期。
    """
    task_id = str(uuid.uuid4())
    new_session_id = body.session_id or str(uuid.uuid4())
    GEN_TASKS[task_id] = _GenTask()
    GEN_TASKS[task_id].session_id = new_session_id
    GEN_TASKS[task_id].question = body.question.strip()
    GEN_TASKS[task_id].kb_id = kb_id
    GEN_TASKS[task_id].user_id = user_id
    GEN_TASKS[task_id].mode = "knowledge" if mode == "knowledge" else "chat"
    question = body.question.strip()
    history = body.history
    enable_reasoning = body.enable_reasoning
    system_prompt = body.system_prompt
    skill_name = body.skill_name
    # 预建会话元数据，确保左侧列表能立即显示
    try:
        GEN_TASKS[task_id]._session_id = new_session_id
    except Exception:
        pass

    if mode == "knowledge":
        def gen():
            yield from rag.answer_stream(
                kb_id, question, history, user_id=user_id, enable_reasoning=enable_reasoning
            )
        target_mode = "knowledge"
    else:
        def gen():
            yield from rag.chat_stream(
                question, system_prompt, history, user_id=user_id, enable_reasoning=enable_reasoning
            )
        target_mode = "chat"

    def on_done():
        # 后台生成结束后，仅做轻量清理/日志；DB 持久化由前端收到 done 事件时
        # 在 finishStreaming 中完成（_save_chat_round），避免后台线程直接操作 DB 的线程安全问题。
        logger.info(f"[GenTask] {task_id} 生成结束（session={new_session_id}）")

    t = threading.Thread(
        target=_run_gen_task,
        args=(task_id, gen, on_done),
        daemon=True,
    )
    t.start()
    return task_id, new_session_id, target_mode


_ALLOWED_EXT = {".txt", ".md", ".markdown", ".pdf", ".docx"}


class KBBase(BaseModel):
    name: str
    description: str = ""


class KBQuery(BaseModel):
    question: str
    session_id: str = None
    mode: str = None
    system_prompt: str = None
    history: list[dict] = []
    enable_reasoning: bool = False
    skill_name: Optional[str] = None
    user_id: Optional[str] = None


def _get_store() -> TaskStore:
    return get_task_store()


@router.get("/knowledge-bases/", summary="列出知识库")
def list_bases(store: TaskStore = Depends(_get_store)):
    items = store.list_knowledge_bases()
    return {"items": items, "total": len(items)}


@router.post("/knowledge-bases/", summary="创建知识库", status_code=201)
def create_base(
    body: KBBase,
    current_user=Depends(require_non_viewer),
    store: TaskStore = Depends(_get_store),
):
    if not body.name.strip():
        raise HTTPException(status_code=400, detail="知识库名称不能为空")
    return store.create_knowledge_base(body.name.strip(), body.description.strip())


@router.get("/knowledge-bases/{kb_id}/", summary="获取知识库详情")
def get_base(kb_id: str, store: TaskStore = Depends(_get_store)):
    kb = store.get_knowledge_base(kb_id)
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")
    return kb


@router.delete("/knowledge-bases/{kb_id}/", summary="删除知识库")
def delete_base(
    kb_id: str,
    current_user=Depends(require_non_viewer),
    store: TaskStore = Depends(_get_store),
):
    kb = store.get_knowledge_base(kb_id)
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")
    try:
        store_dim = rag.get_embedding_provider().dim
        vs = get_vector_store(f"kb_{kb_id}", dim=store_dim)
        vs.clear()
    except Exception as e:
        logger.warning(f"[KB] 清理向量失败: {e}")
    store.delete_knowledge_base(kb_id)
    return {"ok": True}


@router.post("/knowledge-bases/{kb_id}/upload_document/", summary="上传文档到知识库")
async def upload_document(
    kb_id: str,
    file: UploadFile = File(...),
    current_user=Depends(require_non_viewer),
    store: TaskStore = Depends(_get_store),
):
    kb = store.get_knowledge_base(kb_id)
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in _ALLOWED_EXT:
        raise HTTPException(status_code=400, detail="仅支持 .txt / .md / .markdown / .pdf / .docx 文档")

    raw_bytes = await file.read()
    file_size = len(raw_bytes)

    # 按文件类型提取纯文本
    if ext in {".txt", ".md", ".markdown"}:
        content = raw_bytes.decode("utf-8", errors="ignore")
    elif ext == ".pdf":
        if not _PDF_AVAILABLE:
            raise HTTPException(
                status_code=400,
                detail="PDF 解析依赖未安装，请在后端执行：pip install pdfplumber",
            )
        try:
            content = _extract_pdf_text(BytesIO(raw_bytes))
        except Exception as e:
            logger.error(f"[KB] PDF 解析失败: {e}")
            raise HTTPException(status_code=400, detail=f"PDF 解析失败: {e}")
    elif ext == ".docx":
        if not _DOCX_AVAILABLE:
            raise HTTPException(
                status_code=400,
                detail="Word 解析依赖未安装，请在后端执行：pip install python-docx",
            )
        try:
            content = _extract_docx_text(BytesIO(raw_bytes))
        except Exception as e:
            logger.error(f"[KB] Word 解析失败: {e}")
            raise HTTPException(status_code=400, detail=f"Word 解析失败: {e}")
    else:
        content = ""

    if not content.strip():
        raise HTTPException(status_code=400, detail="文档内容为空或无法提取文本")

    try:
        result = rag.ingest_document(kb_id, file.filename, content)
    except Exception as e:
        logger.error(f"[KB] 入库失败: {e}")
        raise HTTPException(status_code=500, detail=f"文档处理失败: {e}")

    chunk_count = result.get("chunks", 0)
    file_type = ext.lstrip(".")
    try:
        doc = store.create_document(
            kb_id=kb_id,
            filename=file.filename,
            file_size=file_size,
            file_type=file_type,
            chunk_count=chunk_count,
        )
    except Exception as e:
        logger.warning(f"[KB] 保存文档记录失败: {e}")
        doc = None

    try:
        vs = get_vector_store(f"kb_{kb_id}", dim=rag.get_embedding_provider().dim)
        store.update_knowledge_base_stats(
            kb_id,
            doc_count=kb["doc_count"] + 1,
            chunk_count=vs.count(),
        )
    except Exception as e:
        logger.warning(f"[KB] 更新统计失败: {e}")

    return {
        "ok": True,
        "filename": file.filename,
        "doc_id": doc["doc_id"] if doc else None,
        **result,
    }


@router.get("/documents/", summary="列出知识库文档")
def list_documents(
    knowledge_base: str,
    current_user=Depends(get_current_user),
    store: TaskStore = Depends(_get_store),
):
    kb = store.get_knowledge_base(knowledge_base)
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")
    rows = store.list_documents(knowledge_base)
    results = []
    for r in rows:
        results.append({
            "id": r["doc_id"],
            "title": r["filename"],
            "file_type": r["file_type"],
            "file_size": r["file_size"],
            "chunk_count": r["chunk_count"],
            "uploaded_at": r["created_at"],
        })
    return {"results": results, "total": len(results)}


@router.delete("/documents/{doc_id}/", summary="删除知识库文档")
def delete_document(
    doc_id: str,
    current_user=Depends(require_non_viewer),
    store: TaskStore = Depends(_get_store),
):
    doc = store.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    kb_id = doc["kb_id"]
    kb = store.get_knowledge_base(kb_id)
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")

    try:
        vs = get_vector_store(f"kb_{kb_id}", dim=rag.get_embedding_provider().dim)
        # chunk id 格式: {kb_id}:{base}:{i}, base = md5(filename)[:8]
        import hashlib
        base = hashlib.md5(doc["filename"].encode("utf-8")).hexdigest()[:8]
        # 删除该文件所有 chunk，最多删除 doc["chunk_count"] 个；若 chunk_count 为 0 则兜底 1000
        max_chunks = doc["chunk_count"] if doc["chunk_count"] > 0 else 1000
        ids_to_delete = [f"{kb_id}:{base}:{i}" for i in range(max_chunks)]
        vs.delete(ids_to_delete)
    except Exception as e:
        logger.warning(f"[KB] 清理向量失败: {e}")

    store.delete_document(doc_id)
    try:
        vs = get_vector_store(f"kb_{kb_id}", dim=rag.get_embedding_provider().dim)
        store.update_knowledge_base_stats(
            kb_id,
            doc_count=max(kb["doc_count"] - 1, 0),
            chunk_count=vs.count(),
        )
    except Exception as e:
        logger.warning(f"[KB] 更新统计失败: {e}")

    return {"ok": True}


@router.post("/knowledge-bases/{kb_id}/ask/", summary="基于知识库问答")
def ask_kb(
    kb_id: str,
    body: KBQuery,
    current_user=Depends(get_current_user),
    store: TaskStore = Depends(_get_store),
):
    kb = store.get_knowledge_base(kb_id)
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")
    if not body.question.strip():
        raise HTTPException(status_code=400, detail="问题不能为空")

    user_id = str(body.user_id or current_user.get("user_id", current_user.get("username", "anonymous")))
    try:
        result = rag.answer(kb_id, body.question.strip(), body.history, user_id=user_id, enable_reasoning=body.enable_reasoning)
    except Exception as e:
        logger.error(f"[KB] 问答失败: {e}")
        raise HTTPException(status_code=500, detail=f"问答失败: {e}")
    return {
        "answer": result.get("answer", ""),
        "sources": result.get("sources", []),
        "context_docs": result.get("sources", []),
        "eval_score": result.get("eval_score"),
        "eval_iterations": result.get("eval_iterations"),
        "needs_human": result.get("needs_human", False),
    }


def _sse_event(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


@router.post("/knowledge-bases/{kb_id}/ask_stream/", summary="基于知识库流式问答（后台任务+多消费者）")
def ask_kb_stream(
    kb_id: str,
    body: KBQuery,
    current_user=Depends(get_current_user),
    store: TaskStore = Depends(_get_store),
):
    kb = store.get_knowledge_base(kb_id)
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")
    if not body.question.strip():
        raise HTTPException(status_code=400, detail="问题不能为空")

    user_id = str(body.user_id or current_user.get("user_id", current_user.get("username", "")))
    # 创建后台生成任务；本请求作为第一个消费者，从 offset=0 拉取全部增量
    task_id, new_session_id, _mode = _start_gen_task(kb_id, body, user_id, mode="knowledge")

    def event_generator():
        # 首包先回 meta（含 task_id，供前端重连使用）
        yield _sse_event({"type": "meta", "session_id": new_session_id, "task_id": task_id})
        for ev in _consume_generator(task_id, offset=0):
            yield ev

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/chat/stream/", summary="日常对话流式问答（后台任务+多消费者）")
def chat_stream(
    body: KBQuery,
    current_user=Depends(get_current_user),
    store: TaskStore = Depends(_get_store),
):
    if not body.question.strip():
        raise HTTPException(status_code=400, detail="问题不能为空")

    user_id = str(body.user_id or current_user.get("user_id", current_user.get("username", "")))
    task_id, new_session_id, _mode = _start_gen_task(None, body, user_id, mode="chat")

    def event_generator():
        yield _sse_event({"type": "meta", "session_id": new_session_id, "task_id": task_id})
        for ev in _consume_generator(task_id, offset=0):
            yield ev

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/chat/task/{task_id}/stream", summary="重连后台生成任务流（切回页面时调用）")
def reconnect_task_stream(task_id: str, offset: int = 0):
    """前端切换页面/会话后，用 task_id 从断点 offset 继续接收增量事件。"""
    if task_id not in GEN_TASKS:
        return StreamingResponse(
            iter([_sse_event({"type": "error", "message": "任务不存在或已过期"})]),
            media_type="text/event-stream",
        )

    def event_generator():
        for ev in _consume_generator(task_id, offset=offset):
            yield ev

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/chat/task/{task_id}/result", summary="查询后台生成任务结果（脱离 SSE 的轻量轮询）")
def get_task_result(task_id: str):
    """
    前端切换页面/会话后，不重连 SSE，而是轮询本接口获取任务结果：
    - done=True 且 full_answer 非空：直接渲染完整答案，无需再占用长连接；
    - done=False：前端标记“生成中”并继续轮询；
    - 任务不存在：返回 exists=False，前端回退到历史记录加载。
    """
    task = GEN_TASKS.get(task_id)
    if task is None:
        return {"exists": False, "done": False, "error": None, "full_answer": "", "events_count": 0}
    with task.lock:
        return {
            "exists": True,
            "done": task.done,
            "error": task.error,
            "full_answer": task.full_answer,
            "events_count": len(task.events),
        }


@router.get("/knowledge-bases/{kb_id}/chat_history/", summary="知识库会话历史")
def chat_history(
    kb_id: str,
    current_user=Depends(get_current_user),
    store: TaskStore = Depends(_get_store),
):
    user_id = str(current_user.get("user_id", current_user.get("username", "")))
    items = store.get_chat_sessions(user_id=user_id, mode="knowledge", kb_id=kb_id, limit=50)
    return {"items": items, "total": len(items)}


@router.get("/knowledge-bases/{kb_id}/session_list/", summary="知识库会话列表")
def session_list(
    kb_id: str,
    current_user=Depends(get_current_user),
    store: TaskStore = Depends(_get_store),
):
    user_id = str(current_user.get("user_id", current_user.get("username", "")))
    items = store.get_chat_sessions(user_id=user_id, mode="knowledge", kb_id=kb_id, limit=50)
    return {"items": items, "total": len(items)}


@router.get("/knowledge-bases/{kb_id}/session_messages/", summary="知识库会话消息")
def session_messages(
    kb_id: str,
    session_id: str,
    current_user=Depends(get_current_user),
    store: TaskStore = Depends(_get_store),
):
    user_id = str(current_user.get("user_id", current_user.get("username", "")))
    # 简单鉴权：确认会话属于当前用户
    sessions = store.get_chat_sessions(user_id=user_id, mode="knowledge", kb_id=kb_id)
    if not any(s.get("session_id") == session_id for s in sessions):
        raise HTTPException(status_code=404, detail="会话不存在")
    items = store.get_chat_messages(session_id)
    return {"items": items, "total": len(items)}


@router.delete("/knowledge-bases/{kb_id}/delete_session/", summary="删除知识库会话")
def delete_session(
    kb_id: str,
    body: dict,
    current_user=Depends(get_current_user),
    store: TaskStore = Depends(_get_store),
):
    session_id = body.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="缺少 session_id")
    user_id = str(current_user.get("user_id", current_user.get("username", "")))
    sessions = store.get_chat_sessions(user_id=user_id, mode="knowledge", kb_id=kb_id)
    matched = next((s for s in sessions if s.get("session_id") == session_id), None)
    # 兼容旧数据：早期保存的知识库会话 kb_id 为空，按 URL 的 kb_id 查不到；
    # 若该会话属于当前用户且 mode=knowledge，则允许删除。
    if matched is None:
        all_knowledge = store.get_chat_sessions(user_id=user_id, mode="knowledge")
        matched = next((s for s in all_knowledge if s.get("session_id") == session_id), None)
    if matched is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    store.delete_chat_session(session_id)
    return {"ok": True}


# ── 日常对话独立会话接口（无 kb_id） ──

@router.get("/chat/history/", summary="日常对话历史")
def chat_history_chat(
    current_user=Depends(get_current_user),
    store: TaskStore = Depends(_get_store),
):
    user_id = str(current_user.get("user_id", current_user.get("username", "")))
    items = store.get_chat_sessions(user_id=user_id, mode="chat", limit=50)
    return {"items": items, "total": len(items)}


@router.get("/chat/sessions/", summary="日常对话会话列表")
def chat_session_list(
    current_user=Depends(get_current_user),
    store: TaskStore = Depends(_get_store),
):
    user_id = str(current_user.get("user_id", current_user.get("username", "")))
    items = store.get_chat_sessions(user_id=user_id, mode="chat", limit=50)
    return {"items": items, "total": len(items)}


@router.get("/chat/messages/", summary="日常对话会话消息")
def chat_session_messages(
    session_id: str,
    current_user=Depends(get_current_user),
    store: TaskStore = Depends(_get_store),
):
    user_id = str(current_user.get("user_id", current_user.get("username", "")))
    sessions = store.get_chat_sessions(user_id=user_id, mode="chat")
    if not any(s.get("session_id") == session_id for s in sessions):
        raise HTTPException(status_code=404, detail="会话不存在")
    items = store.get_chat_messages(session_id)
    return {"items": items, "total": len(items)}


@router.delete("/chat/sessions/{session_id}/", summary="删除日常对话会话")
def delete_chat_session_endpoint(
    session_id: str,
    current_user=Depends(get_current_user),
    store: TaskStore = Depends(_get_store),
):
    user_id = str(current_user.get("user_id", current_user.get("username", "")))
    sessions = store.get_chat_sessions(user_id=user_id, mode="chat")
    if not any(s.get("session_id") == session_id for s in sessions):
        raise HTTPException(status_code=404, detail="会话不存在")
    store.delete_chat_session(session_id)
    return {"ok": True}
