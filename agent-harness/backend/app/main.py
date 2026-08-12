"""
AI 编排服务入口

目标：Django 发起请求 -> FastAPI 编排服务执行 -> SSE 流式返回 -> 前端无感知

W2 新增：
- OpenTelemetry Trace 自动埋点 + 手动跨服务传播
- /metrics 端点供 Prometheus 采集
- 优雅关停（Graceful Shutdown）
- K8s 兼容的 liveness / readiness 探针
"""
# 最先加载 .env，确保所有环境变量在导入前就绪
from pathlib import Path
from dotenv import load_dotenv

# 1) 优先加载 backend 自身目录下的 .env（如果存在）
_backend_env = Path(__file__).resolve().parent.parent / ".env"
# 2) 否则回退到项目根目录 .env（兼容旧项目结构）
# backend 路径: agent-harness/backend/app/main.py -> agent-harness/backend -> agent-harness -> ai-test-platform
_root_env = Path(__file__).resolve().parent.parent.parent.parent / ".env"
_env_file = _backend_env if _backend_env.exists() else (_root_env if _root_env.exists() else None)
if _env_file:
    load_dotenv(_env_file, override=True)
    print(f"[ENV] Loaded env file: {_env_file}", flush=True)

import contextvars
import json
import logging
import os
import signal
import sys
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.v1.router import api_router
from app.core.telemetry import setup_tracer_provider, inject_trace_context
from app.core.metrics import metrics_response, REGISTRY
from app.core.middleware import PrometheusMetricsMiddleware, GracefulShutdownMiddleware
from app.core.auth import AuthMiddleware

# ============================================================
# 结构化日志：JSON 格式 + trace_id 注入
# ============================================================

_request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar(
    "orchestrator_request_id", default=""
)


def get_request_id() -> str:
    return _request_id_ctx.get() or "-"


class RequestIDFilter(logging.Filter):
    """将 trace_id 注入 LogRecord"""
    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = get_request_id()
        return True


class JSONFormatter(logging.Formatter):
    """结构化 JSON 日志格式，与 Django 端一致"""
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "level": record.levelname,
            "logger": record.name,
            "trace_id": getattr(record, "trace_id", "-"),
            "message": record.getMessage(),
            "module": record.module,
            "funcName": record.funcName,
            "lineno": record.lineno,
        }
        if record.exc_info and record.exc_info[0]:
            log_entry["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, ensure_ascii=False)


# -- 配置 root logger --
_handler = logging.StreamHandler()
_handler.setFormatter(JSONFormatter())
_handler.addFilter(RequestIDFilter())

_root_logger = logging.getLogger()
_root_logger.handlers.clear()
_root_logger.addHandler(_handler)
_root_logger.setLevel(logging.INFO)

logger = logging.getLogger(__name__)

# ============================================================
# OpenTelemetry 初始化
# ============================================================

try:
    setup_tracer_provider()
    logger.info("[Telemetry] OpenTelemetry tracer initialized")
except Exception as e:
    logger.warning(f"[Telemetry] OpenTelemetry init failed: {e}")

# ============================================================
# 优雅关停：信号处理
# ============================================================


def _handle_signal(signum, frame):
    """处理 SIGTERM/SIGINT，触发优雅关停"""
    GracefulShutdownMiddleware.mark_shutting_down()
    logger.info(f"[Signal] Received {signal.Signals(signum).name}, graceful shutdown started")


# 开发/演示环境关闭优雅关停信号捕获，避免 Windows 控制台信号误杀服务
# 生产环境可设置 GRACEFUL_SHUTDOWN=1 启用
if os.getenv("GRACEFUL_SHUTDOWN", "0") == "1":
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)
    logger.info("[Signal] 生产模式：已注册优雅关停信号处理器")
else:
    logger.info("[Signal] 开发模式：跳过优雅关停信号处理器（Windows 演示更稳定）")

# ============================================================
# 请求级 trace_id 中间件（兼容上游 X-Request-ID）
# ============================================================

class RequestIDMiddleware(BaseHTTPMiddleware):
    """请求级 trace_id 注入（兼容上游 X-Request-ID）"""
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", "").strip()
        if not request_id:
            request_id = str(uuid.uuid4())
        _request_id_ctx.set(request_id)

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


# ============================================================
# Lifespan：启动/关停事件
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理：启动 -> 运行 -> 优雅关停"""
    # Phase 2.1：启动时初始化 TaskStore（建表 + 种子数据）
    from app.core.task_store import get_task_store
    store = get_task_store()
    logger.info(f"[TaskStore] 已就绪 db={store.db_path}")

    # 防御性重置：避免上次异常退出后 _shutting_down 仍为 True
    # （uvicorn reload 场景下中间件类变量不会自动复位）
    GracefulShutdownMiddleware.mark_startup_complete()
    logger.info("[AI Orchestration Service] 启动完成")
    yield
    logger.info("[AI Orchestration Service] 开始关停...")
    await GracefulShutdownMiddleware.wait_for_requests()
    logger.info("[AI Orchestration Service] 关停完成")


# ============================================================
# FastAPI 应用
# ============================================================

app = FastAPI(
    title="AI Orchestration Service",
    description="Agent Harness 编排服务 — Plan → Orchestrate → Verify",
    version="0.1.0",
    lifespan=lifespan,
)

# 注意 Starlette 中间件是洋葱模型：先 add 的在最内层，后 add 的在外层。
# 请求进入顺序（外层 → 内层）：GracefulShutdown → Prometheus → CORS → Auth → RequestID → app
# 因此 add 顺序要与进入顺序相反：RequestID → Auth → CORS → Prometheus → GracefulShutdown
app.add_middleware(RequestIDMiddleware)
app.add_middleware(AuthMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(PrometheusMetricsMiddleware)
app.add_middleware(GracefulShutdownMiddleware)

app.include_router(api_router, prefix="/api/v1")

# ============================================================
# Prometheus 指标端点
# ============================================================

@app.get("/metrics")
async def metrics():
    """Prometheus 采集端点"""
    data, content_type = metrics_response()
    return Response(content=data, media_type=content_type)


# ============================================================
# OpenTelemetry 自动埋点（要在路由注册之后）
# ============================================================

try:
    FastAPIInstrumentor.instrument_app(
        app,
        excluded_urls="/metrics,/health",
    )
    logger.info("[Telemetry] FastAPI instrumentation enabled")
except Exception as e:
    logger.warning(f"[Telemetry] FastAPI instrumentation failed: {e}")


# ============================================================
# 本地启动入口
# ============================================================

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8001")),
        # 生产环境由 gunicorn/uvicorn worker 管理，此处仅作本地开发
        lifespan="on",
    )
