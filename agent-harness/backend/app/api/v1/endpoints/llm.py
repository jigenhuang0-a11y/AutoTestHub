import json
import logging
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field

from app.schemas.llm import LLMChatRequest, LLMChatStreamRequest
from app.core.router import get_llm_router
from app.core.metrics import workflow_total
from app.core.telemetry import get_tracer
from app.core.config import security_config
from app.core.security import PromptGuard, OutputGuard
from app.core.auth import JWTUser, get_current_user
from app.core.task_store import get_task_store

logger = logging.getLogger(__name__)
router = APIRouter()
tracer = get_tracer(__name__)

# 安全守卫实例
_prompt_guard = PromptGuard(
    reject_threshold=security_config.prompt_guard_threshold,
    max_input_length=security_config.max_input_length,
)
_output_guard = OutputGuard(block_critical=security_config.output_block_critical)


@router.post("/chat")
async def llm_chat(
    request: LLMChatRequest,
    user: JWTUser = Depends(get_current_user),
):
    """
    同步 LLM 对话（底座 LLMRouter 唯一入口）

    所有 LLM 调用统一经由此端点，包括 Django agent_gateway 的 invoke 动作。
    底座 LLMRouter 负责模型路由、Provider 降级、超时保护。

    鉴权：需通过 AuthMiddleware（Bearer JWT 或 X-Service-Token）。
    """
    logger.info(
        f"[LLM] /chat user_id={user.user_id} username={user.username} "
        f"auth={user.auth_method} task_type={request.task_type}"
    )
    # ====== 安全层：Prompt 注入检测 ======
    if security_config.prompt_guard_enabled:
        with tracer.start_as_current_span("security.prompt_guard") as guard_span:
            guard_result = _prompt_guard.check(request.messages)
            guard_span.set_attribute("security.score", guard_result.score)
            guard_span.set_attribute("security.blocked", not guard_result.is_safe)
            if not guard_result.is_safe:
                logger.warning(
                    f"[Security] Prompt 注入拦截 | "
                    f"score={guard_result.score} | "
                    f"patterns={guard_result.blocked_patterns} | "
                    f"msg_preview={str(request.messages)[:200]}"
                )
                workflow_total.labels(status="blocked", mode="llm_chat").inc()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"error": "REQUEST_BLOCKED", "reason": guard_result.reason},
                )

    router_instance = get_llm_router()
    workflow_total.labels(status="started", mode="llm_chat").inc()

    try:
        with tracer.start_as_current_span("llm.chat") as span:
            span.set_attribute("task_type", request.task_type)
            answer = router_instance.chat(
                messages=request.messages,
                task_type=request.task_type,
                model=request.model,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
            )

        # ====== 安全层：输出内容过滤 ======
        if security_config.output_guard_enabled:
            with tracer.start_as_current_span("security.output_guard") as guard_span:
                output_result = _output_guard.scan(answer)
                guard_span.set_attribute("security.violations", len(output_result.violations))
                if not output_result.is_safe:
                    logger.warning(
                        f"[Security] 输出拦截 | violations={output_result.violations} | "
                        f"answer_preview={answer[:200]}"
                    )
                    workflow_total.labels(status="blocked", mode="llm_chat").inc()
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail={"error": "OUTPUT_BLOCKED", "reason": str(output_result.violations)},
                    )
                answer = output_result.cleaned_text

        workflow_total.labels(status="completed", mode="llm_chat").inc()
        return {
            "answer": answer,
            "model_used": str(request.model or "auto"),
        }
    except HTTPException:
        raise
    except Exception as e:
        workflow_total.labels(status="failed", mode="llm_chat").inc()
        logger.exception(f"[LLMEndpoint] chat 失败: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": str(e)},
        )


@router.post("/chat/stream")
async def llm_chat_stream(
    request: LLMChatStreamRequest,
    user: JWTUser = Depends(get_current_user),
):
    """
    SSE 流式 LLM 对话（底座 LLMRouter 唯一流式入口）

    鉴权：需通过 AuthMiddleware（Bearer JWT 或 X-Service-Token）。

    安全：输入层 Prompt 注入检测（流式输出安全过滤因技术限制暂缓，
          目前依赖 LLM 自身对齐能力；后续考虑按 chunk 异步过滤）。
    """
    logger.info(
        f"[LLM] /chat/stream user_id={user.user_id} username={user.username} "
        f"auth={user.auth_method} task_type={request.task_type}"
    )
    # ====== 安全层：Prompt 注入检测 ======
    if security_config.prompt_guard_enabled:
        with tracer.start_as_current_span("security.prompt_guard") as guard_span:
            guard_result = _prompt_guard.check(request.messages)
            guard_span.set_attribute("security.score", guard_result.score)
            if not guard_result.is_safe:
                logger.warning(
                    f"[Security] Stream Prompt 注入拦截 | "
                    f"score={guard_result.score} | "
                    f"patterns={guard_result.blocked_patterns} | "
                    f"msg_preview={str(request.messages)[:200]}"
                )
                workflow_total.labels(status="blocked", mode="llm_chat_stream").inc()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"error": "REQUEST_BLOCKED", "reason": guard_result.reason},
                )

    router_instance = get_llm_router()

    def generate():
        # 流式安全：逐 chunk 实时脱敏 + 整段复核
        # - 单 chunk 内完整命中的敏感串立即打码，保持低延迟
        # - 累积全文本，done 时整段审计复核（覆盖跨 chunk 拼接才暴露的串）
        full_text = []
        try:
            for chunk in router_instance.chat_stream(
                messages=request.messages,
                task_type=request.task_type,
                model=request.model,
            ):
                clean = chunk
                if security_config.output_guard_enabled and chunk:
                    res = _output_guard.scan(chunk)
                    if res.violations:
                        clean = res.cleaned_text
                        logger.warning(
                            f"[Security] 流式输出实时脱敏 | violations={res.violations}"
                        )
                full_text.append(clean)
                yield f"data: {json.dumps({'chunk': clean}, ensure_ascii=False)}\n\n"

            # 整段复核：跨 chunk 拼接才会暴露的敏感信息
            if security_config.output_guard_enabled and full_text:
                whole = "".join(full_text)
                res = _output_guard.scan(whole)
                if res.violations:
                    logger.warning(
                        f"[Security] 流式整段审计命中 | violations={res.violations}"
                    )
                    if not res.is_safe:
                        # 已流出部分无法撤回，记录审计失败事件
                        yield f"data: {json.dumps({'error': 'OUTPUT_BLOCKED: ' + str(res.violations)}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.exception(f"[LLMEndpoint] stream 失败: {e}")
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/models")
async def llm_models(user: JWTUser = Depends(get_current_user)):
    """列出所有可用模型（需鉴权）"""
    router_instance = get_llm_router()
    return {"models": router_instance.get_available_models()}


# ── SaaS：团队模型偏好管理 ──

class TeamModelPrefsUpdate(BaseModel):
    """团队模型偏好 — 只需传要覆盖的字段，留空表示用全局默认"""
    planning_model: str = ""
    code_generation_model: str = ""
    evaluation_model: str = ""
    agent_model: str = ""
    fast_chat_model: str = ""
    data_generation_model: str = ""
    rag_query_model: str = ""
    fallback_model: str = ""


class TeamModelPrefsResponse(BaseModel):
    team_id: str
    prefs: dict


@router.get("/team/{team_id}/model-prefs")
async def get_team_model_prefs(
    team_id: str, user: JWTUser = Depends(get_current_user)
):
    """获取团队的模型偏好设置（SaaS 核心功能）"""
    store = get_task_store()
    prefs = store.get_team_model_prefs(team_id)
    if prefs is None:
        return TeamModelPrefsResponse(team_id=team_id, prefs={
            "planning_model": "",
            "code_generation_model": "",
            "evaluation_model": "",
            "agent_model": "",
            "fast_chat_model": "",
            "data_generation_model": "",
            "rag_query_model": "",
            "fallback_model": "",
        })
    return TeamModelPrefsResponse(team_id=team_id, prefs=prefs.to_dict())


@router.put("/team/{team_id}/model-prefs")
async def set_team_model_prefs(
    team_id: str,
    config: TeamModelPrefsUpdate = Body(...),
    user: JWTUser = Depends(get_current_user),
):
    """
    设置团队的模型偏好（SaaS 核心功能）。
    传空字符串的字段表示"不覆盖，使用全局默认"。
    """
    if user.role == "viewer":
        raise HTTPException(status_code=403, detail="访客模式不支持此操作")
    store = get_task_store()
    update_data = {k: v for k, v in config.model_dump().items() if k != "id"}
    prefs = store.set_team_model_prefs(team_id, **update_data)
    return {"status": "ok", "team_id": team_id, "prefs": prefs.to_dict()}


@router.delete("/team/{team_id}/model-prefs")
async def delete_team_model_prefs(
    team_id: str, user: JWTUser = Depends(get_current_user)
):
    """删除团队模型偏好（恢复全局默认）"""
    if user.role == "viewer":
        raise HTTPException(status_code=403, detail="访客模式不支持此操作")
    store = get_task_store()
    deleted = store.delete_team_model_prefs(team_id)
    return {"status": "ok" if deleted else "not_found", "team_id": team_id}
