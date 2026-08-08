"""FastAPI 入口：Agent Harness 中台内核启动点。

P0 阶段只做骨架：健康检查 + 配置自检 + 路由挂载占位。
禁止在 P0 写任何 Agent 调度逻辑（红线：底座以跑通业务链路为终点）。
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from harness_core.config import settings
from harness_core.logging import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动自检
    logger.info(f"启动 {settings.app_name} | env={settings.env} | 版本骨架 P0")
    missing = _check_required_config()
    if missing:
        logger.warning(f"以下配置项为空（P0 可忽略，P1 前必须补全）: {missing}")
    yield
    logger.info("Agent Harness Core 关闭")


def _check_required_config() -> list[str]:
    required = ["deepseek_api_key"]
    return [k for k in required if not getattr(settings, k)]


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "service": settings.app_name,
        "env": settings.env,
        "phase": "P0-scaffold",
    }


# TODO(P1): 挂载 API 路由
# from harness_core.api import router as api_router
# app.include_router(api_router, prefix=settings.api_prefix)
