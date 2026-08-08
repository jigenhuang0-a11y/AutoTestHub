"""统一配置中心：所有环境变量与运行时配置的唯一入口。

设计原则：
- 密钥一律从环境变量读取，禁止硬编码（见 .env.example）。
- 配置对象全局单例，启动时校验必填项。
- 分层：app / mysql / redis / milvus / llm / sandbox。
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

EnvMode = Literal["dev", "prod", "test"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # ---- 应用 ----
    app_name: str = "Agent Harness Core"
    env: EnvMode = "dev"
    host: str = "0.0.0.0"
    port: int = 8001
    debug: bool = True
    api_prefix: str = "/api/v1"

    # ---- MySQL（业务/元数据）----
    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_user: str = "harness"
    mysql_password: str = "harness_dev"
    mysql_database: str = "harness_core"
    mysql_echo: bool = False

    # ---- Redis（限流/缓存/异步队列）----
    redis_url: str = "redis://127.0.0.1:6379/0"

    # ---- Milvus（向量）----
    milvus_host: str = "127.0.0.1"
    milvus_port: int = 19530
    milvus_token: str = ""

    # ---- 统一模型底座 ----
    # 多模型适配器：DeepSeek 主力，通义千问备用
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"

    qwen_api_key: str = ""
    qwen_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    qwen_model: str = "qwen-plus"

    # ---- 配额/限流/熔断 ----
    default_token_quota: int = 1_000_000  # 每 Agent 每日 Token 额度
    default_qps_limit: int = 5            # 每 Agent 每秒请求上限
    circuit_breaker_failures: int = 5     # 连续失败触发熔断次数
    circuit_breaker_reset_seconds: int = 60

    # ---- OpenClaw 沙箱（P2 实装，P0/P1 先用本地进程兜底）----
    sandbox_enabled: bool = False         # False = 本地进程执行
    sandbox_docker_image: str = "harness-sandbox:latest"
    sandbox_cpu_limit: float = 1.0
    sandbox_memory_mb: int = 256
    sandbox_timeout_seconds: int = 30

    # ---- 安全护栏 ----
    guardrail_prompt_injection_check: bool = True
    guardrail_output_moderation: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
