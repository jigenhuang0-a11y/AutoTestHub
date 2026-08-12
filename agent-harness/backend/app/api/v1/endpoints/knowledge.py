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
from io import BytesIO

import json
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
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


@router.post("/knowledge-bases/{kb_id}/ask_stream/", summary="基于知识库流式问答")
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
    question = body.question.strip()
    session_id = body.session_id
    # 新会话时提前生成稳定的 session_id，确保 meta 事件返回与持久化写入的 id 一致
    new_session_id = session_id or str(uuid.uuid4())
    full_answer_parts: list[str] = []

    def event_generator():
        nonlocal full_answer_parts
        eval_score = None
        needs_human = False
        yield _sse_event({"type": "meta", "session_id": new_session_id})
        yield _sse_event({"type": "status", "content": "正在检索知识库..."})
        try:
            for event in rag.answer_stream(kb_id, question, body.history, user_id=user_id, enable_reasoning=body.enable_reasoning):
                if event.get("type") == "delta":
                    full_answer_parts.append(event.get("content", ""))
                if event.get("type") == "done":
                    eval_score = event.get("eval_score")
                    needs_human = bool(event.get("needs_human"))
                yield _sse_event(event)
                if event.get("type") == "error":
                    return
        except Exception as e:
            logger.error(f"[KB] ask_stream 失败: {e}")
            yield _sse_event({"type": "error", "message": f"问答失败: {e}"})
            return
        yield _sse_event("[DONE]")
        # SSE 结束后持久化会话（同步执行，不影响流式返回）
        try:
            saved_sid = _save_chat_round(
                store=store,
                user_id=user_id,
                question=question,
                answer="".join(full_answer_parts),
                mode="knowledge",
                session_id=new_session_id,
                kb_id=kb_id,
                eval_score=eval_score,
                needs_human=needs_human,
            )
            logger.info(f"[KB] 已保存知识库会话 {saved_sid}")
        except Exception as e:
            logger.warning(f"[KB] 保存知识库会话失败: {e}")

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/chat/stream/", summary="日常对话流式问答")
def chat_stream(
    body: KBQuery,
    current_user=Depends(get_current_user),
    store: TaskStore = Depends(_get_store),
):
    if not body.question.strip():
        raise HTTPException(status_code=400, detail="问题不能为空")

    user_id = str(body.user_id or current_user.get("user_id", current_user.get("username", "")))
    question = body.question.strip()
    session_id = body.session_id
    # 新会话时提前生成稳定的 session_id，确保 meta 事件返回与持久化写入的 id 一致
    new_session_id = session_id or str(uuid.uuid4())
    full_answer_parts: list[str] = []

    def event_generator():
        nonlocal full_answer_parts
        eval_score = None
        needs_human = False
        yield _sse_event({"type": "meta", "session_id": new_session_id})
        try:
            for event in rag.chat_stream(question, body.system_prompt, body.history, user_id=user_id, enable_reasoning=body.enable_reasoning):
                if event.get("type") == "delta":
                    full_answer_parts.append(event.get("content", ""))
                if event.get("type") == "done":
                    eval_score = event.get("eval_score")
                    needs_human = bool(event.get("needs_human"))
                yield _sse_event(event)
                if event.get("type") == "error":
                    return
        except Exception as e:
            logger.error(f"[KB] chat_stream 失败: {e}")
            yield _sse_event({"type": "error", "message": f"对话失败: {e}"})
            return
        yield _sse_event("[DONE]")
        # SSE 结束后持久化会话
        try:
            saved_sid = _save_chat_round(
                store=store,
                user_id=user_id,
                question=question,
                answer="".join(full_answer_parts),
                mode="chat",
                session_id=new_session_id,
                eval_score=eval_score,
                needs_human=needs_human,
            )
            logger.info(f"[KB] 已保存日常对话会话 {saved_sid}")
        except Exception as e:
            logger.warning(f"[KB] 保存日常对话会话失败: {e}")

    return StreamingResponse(event_generator(), media_type="text/event-stream")


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
    if not any(s["id"] == session_id for s in sessions):
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
    if not any(s["id"] == session_id for s in sessions):
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
    if not any(s["id"] == session_id for s in sessions):
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
    if not any(s["id"] == session_id for s in sessions):
        raise HTTPException(status_code=404, detail="会话不存在")
    store.delete_chat_session(session_id)
    return {"ok": True}
