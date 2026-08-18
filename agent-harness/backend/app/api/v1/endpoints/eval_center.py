"""
全链路评测中心 API

提供：
- 对任意输入/输出执行 Judge LLM 多维评分
- 获取本地聚合的实时监控仪表盘数据
- 返回 Langfuse 外部链接配置
"""
import logging
import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.core.eval_store import get_eval_store
from app.core.hallucination_judge import judge_output

logger = logging.getLogger(__name__)
router = APIRouter()


class JudgeRequest(BaseModel):
    input_text: str = Field(..., description="原始输入 / prompt")
    output_text: str = Field(..., description="模型生成输出")
    reference: str = Field("", description="参考答案 / RAG 检索片段")
    feature: str = Field("unknown", description="业务模块，如 ai_testcase / data_factory / knowledge_chat")
    trace_id: Optional[str] = Field(None, description="关联的 Langfuse trace_id")
    user_id: Optional[str] = Field(None, description="用户 ID")
    session_id: Optional[str] = Field(None, description="会话 ID")


class JudgeResponse(BaseModel):
    success: bool
    data: Dict[str, Any]
    message: str = ""


@router.post("/judge", response_model=JudgeResponse)
def run_judge(req: JudgeRequest):
    """对一次 LLM 生成结果执行 Judge 评分，并本地缓存 + 回传 Langfuse。"""
    try:
        result = judge_output(
            input_text=req.input_text,
            output_text=req.output_text,
            reference=req.reference,
            trace_id=req.trace_id,
            feature=req.feature,
            user_id=req.user_id,
            session_id=req.session_id,
        )
        record = result.to_dict()
        record["feature"] = req.feature
        record["input_text"] = req.input_text[:1000]
        record["output_text"] = req.output_text[:1000]
        get_eval_store().save(record)
        # 显式返回标准包装结构，避免旧镜像/代理返回裸对象
        return {"success": True, "data": record, "message": ""}
    except Exception as e:
        logger.error(f"[eval_center] judge 失败: {e}")
        return JudgeResponse(success=False, data={}, message=str(e))


@router.get("/dashboard")
def get_dashboard(
    hours: int = Query(24, ge=1, le=720),
    granularity: str = Query("auto", pattern="^(auto|hour|day)$"),
):
    """获取评测聚合数据。

    - hours: 统计窗口（1~720 小时，默认 24）
    - granularity: 趋势粒度 auto/hour/day。auto 时若窗口内仅 1 个时间点，自动退化为按天聚合。
    """
    return get_eval_store().get_dashboard(hours=hours, granularity=granularity)


@router.get("/records")
def list_records(
    feature: Optional[str] = Query(None),
    hours: int = Query(24, ge=1, le=720),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """分页查询评测记录。"""
    return get_eval_store().list_records(feature=feature, hours=hours, limit=limit, offset=offset)


@router.get("/langfuse-config")
def get_langfuse_config():
    """返回 Langfuse 外部链接，前端可跳转查看原始 trace。"""
    host = os.getenv("LANGFUSE_HOST", "").rstrip("/")
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    return {
        "enabled": bool(host and public_key),
        "host": host,
        "project_url": f"{host}/project" if host else "",
        "traces_url": f"{host}/traces" if host else "",
    }
