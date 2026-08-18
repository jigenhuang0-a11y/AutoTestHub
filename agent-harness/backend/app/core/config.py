"""
编排服务配置中心

通过环境变量读取，不依赖 Django settings。
"""
import os
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ModelConfig:
    """单个模型配置"""
    name: str
    provider: str
    capabilities: list
    max_tokens: int = 4096
    temperature: float = 0.7
    priority: int = 1


@dataclass
class LLMRouterConfig:
    """LLM 路由配置"""

    route_map: dict = field(default_factory=lambda: {
        "planning": ["deepseek-chat", "qwen-max"],
        "code_generation": ["deepseek-chat", "qwen-plus"],
        "evaluation": ["deepseek-chat", "qwen-max"],
        "agent": ["deepseek-chat", "qwen-plus"],        # ReAct Agent 专用
        "fast_chat": ["deepseek-chat", "qwen-turbo"],   # 日常对话默认走 DeepSeek（本地 Key 可用）
        "chat": ["deepseek-chat", "qwen-turbo"],
        "knowledge_chat": ["deepseek-chat", "qwen-plus"],  # RAG 知识库问答
        "data_generation": ["deepseek-chat", "qwen-plus"],
        "rag_query": ["deepseek-chat", "qwen-plus"],    # 知识库问答默认 DeepSeek
        "reasoning": ["deepseek-chat", "qwen-max"],      # 深度思考优先原生推理模型
        "fallback": ["deepseek-chat", "qwen-turbo"],
    })
    default_model: str = "deepseek-chat"

    def get_model(self, task_type: str, available_providers: set) -> str:
        candidates = self.route_map.get(task_type, [self.default_model])
        for model in candidates:
            provider = _get_provider_name(model)
            if provider in available_providers:
                return model
        return self.default_model


@dataclass
class AgentConfig:
    """Agent 编排配置"""
    max_retries: int = 3
    max_steps: int = 20
    timeout_seconds: int = 300
    max_concurrent_agents: int = 3
    session_ttl_seconds: int = 3600


MODEL_REGISTRY: dict[str, ModelConfig] = {
    "qwen-max": ModelConfig(
        name="qwen-max", provider="dashscope",
        capabilities=["reasoning", "planning", "evaluation"],
        max_tokens=8192, temperature=0.3, priority=3,
    ),
    "qwen-plus": ModelConfig(
        name="qwen-plus", provider="dashscope",
        capabilities=["reasoning", "code_generation", "fast_chat", "rag_query"],
        max_tokens=4096, temperature=0.5, priority=2,
    ),
    "qwen-turbo": ModelConfig(
        name="qwen-turbo", provider="dashscope",
        capabilities=["fast_chat", "fallback"],
        max_tokens=2048, temperature=0.7, priority=1,
    ),
    "deepseek-chat": ModelConfig(
        name="deepseek-chat", provider="deepseek",
        capabilities=["reasoning", "code_generation", "planning", "evaluation"],
        max_tokens=8192, temperature=0.3, priority=3,
    ),
    "glm-4-flash": ModelConfig(
        name="glm-4-flash", provider="glm",
        capabilities=["fast_chat", "code_generation"],
        max_tokens=4096, temperature=0.7, priority=1,
    ),
}


def _get_provider_name(model_name: str) -> str:
    if model_name in MODEL_REGISTRY:
        return MODEL_REGISTRY[model_name].provider
    if model_name.startswith("qwen"):
        return "dashscope"
    if model_name.startswith("deepseek"):
        return "deepseek"
    if model_name.startswith("glm"):
        return "glm"
    return "dashscope"


def get_available_providers() -> set:
    """检查环境变量中已配置的 Provider"""
    available = set()
    if os.getenv("DASHSCOPE_API_KEY"):
        available.add("dashscope")
    if os.getenv("DEEPSEEK_API_KEY"):
        available.add("deepseek")
    if os.getenv("GLM_API_KEY"):
        available.add("glm")
    return available


def get_default_llm_config() -> tuple[LLMRouterConfig, AgentConfig]:
    return LLMRouterConfig(), AgentConfig()


# Redis 地址（用于状态持久化）
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# ============================================================
# JWT 鉴权配置（FastAPI 自签，不再与 Django 互通）
# ============================================================

# 平台自签 JWT 签名密钥（生产环境务必通过环境变量 JWT_SIGNING_KEY 覆盖）
JWT_SIGNING_KEY = os.getenv("JWT_SIGNING_KEY", "dev-local-signing-key-change-in-prod")

# JWT 算法
JWT_ALGORITHM = "HS256"

# 服务间通行令牌（X-Service-Token 通道，供非用户绑定的内部调用）
SERVICE_TOKEN = os.getenv("SERVICE_TOKEN", "")

# 是否强制要求 JWT 已配置才启动（生产环境建议 True）
JWT_REQUIRED = os.getenv("JWT_REQUIRED", "false").lower() == "true"

# ============================================================
# AI 安全配置
# ============================================================

@dataclass
class SecurityConfig:
    """AI 原生安全配置"""

    # Prompt 注入检测开关
    prompt_guard_enabled: bool = True

    # 注入检测：评分阈值（超过此值拒绝请求）
    prompt_guard_threshold: int = 10

    # 输入最大长度（字符）
    max_input_length: int = 32000

    # 输出安全过滤开关
    output_guard_enabled: bool = True

    # 输出检测到严重问题时：True=拒绝整条回复, False=仅脱敏后返回
    output_block_critical: bool = True

    # 是否记录所有安全事件到日志
    audit_log_enabled: bool = True

    @classmethod
    def from_env(cls) -> "SecurityConfig":
        return cls(
            prompt_guard_enabled=os.getenv("SEC_PROMPT_GUARD_ENABLED", "true").lower() == "true",
            prompt_guard_threshold=int(os.getenv("SEC_PROMPT_GUARD_THRESHOLD", "10")),
            max_input_length=int(os.getenv("SEC_MAX_INPUT_LENGTH", "32000")),
            output_guard_enabled=os.getenv("SEC_OUTPUT_GUARD_ENABLED", "true").lower() == "true",
            output_block_critical=os.getenv("SEC_OUTPUT_BLOCK_CRITICAL", "true").lower() == "true",
            audit_log_enabled=os.getenv("SEC_AUDIT_LOG_ENABLED", "true").lower() == "true",
        )


# 模块级安全配置实例
security_config = SecurityConfig.from_env()


# ============================================================
# 沙箱配置（代码执行隔离）
# ============================================================

@dataclass
class SandboxConfigHolder:
    """
    沙箱全局开关与默认策略。
    - enabled=True 时，底座 workflow 的 execution 步骤一律先过沙箱；
      仅在策略文件缺失或沙箱执行系统错误时才回退流程（带审计告警）。
    - enabled=False 时，直接执行（仅用于本地无沙箱调试）。
    """
    enabled: bool = True
    default_timeout_seconds: int = int(os.getenv("SANDBOX_TIMEOUT", "300"))
    default_max_memory_mb: int = int(os.getenv("SANDBOX_MAX_MEMORY_MB", "512"))
    default_max_processes: int = int(os.getenv("SANDBOX_MAX_PROCESSES", "10"))
    policy_dir: str = os.getenv(
        "SANDBOX_POLICY_DIR",
        os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "sandbox_policies",
        ),
    )

    # 从策略文件加载的安全策略（见 load_sandbox_policy）
    allow_network: bool = False
    allowed_hosts: list = field(default_factory=list)
    allowed_write_paths: list = field(default_factory=list)
    read_only_paths: list = field(default_factory=list)
    env_whitelist: list = field(default_factory=list)
    injected_env: dict = field(default_factory=dict)
    policy_loaded: bool = False

    @classmethod
    def from_env(cls) -> "SandboxConfigHolder":
        return cls(
            enabled=os.getenv("SANDBOX_ENABLED", "true").lower() == "true",
        )


def load_sandbox_policy(holder: "SandboxConfigHolder" = None) -> "SandboxConfigHolder":
    """
    读取 sandbox_policies/*.yaml，把安全策略加载进 holder。
    找不到策略文件时降级为"默认拒绝"的安全基线（绝不裸放行）。
    """
    holder = holder or sandbox_config
    import yaml  # 延迟导入，避免无 yaml 时阻塞启动

    policy_file = os.path.join(holder.policy_dir, "default.yaml")
    try:
        if not os.path.exists(policy_file):
            logger.warning(
                f"[Config] 沙箱策略文件缺失: {policy_file}，启用默认拒绝基线"
            )
            holder.allow_network = False
            holder.allowed_hosts = []
            holder.policy_loaded = True
            return holder

        with open(policy_file, "r", encoding="utf-8") as f:
            policy = yaml.safe_load(f) or {}

        # 环境变量优先于文件（便于运维热调）
        if os.getenv("SANDBOX_ENABLED"):
            holder.enabled = os.getenv("SANDBOX_ENABLED").lower() == "true"
        else:
            holder.enabled = bool(policy.get("enabled", holder.enabled))
        if os.getenv("SANDBOX_TIMEOUT"):
            holder.default_timeout_seconds = int(os.getenv("SANDBOX_TIMEOUT"))
        else:
            holder.default_timeout_seconds = int(policy.get("timeout_seconds", holder.default_timeout_seconds))
        if os.getenv("SANDBOX_MAX_MEMORY_MB"):
            holder.default_max_memory_mb = int(os.getenv("SANDBOX_MAX_MEMORY_MB"))
        else:
            holder.default_max_memory_mb = int(policy.get("max_memory_mb", holder.default_max_memory_mb))
        if os.getenv("SANDBOX_MAX_PROCESSES"):
            holder.default_max_processes = int(os.getenv("SANDBOX_MAX_PROCESSES"))
        else:
            holder.default_max_processes = int(policy.get("max_processes", holder.default_max_processes))

        # 安全策略字段
        holder.allow_network = bool(policy.get("allow_network", False))
        holder.allowed_hosts = list(policy.get("allowed_hosts", []) or [])
        holder.allowed_write_paths = list(policy.get("allowed_write_paths", []) or [])
        holder.read_only_paths = list(policy.get("read_only_paths", []) or [])
        holder.env_whitelist = list(
            policy.get("env_whitelist", []) or []
        ) or holder.env_whitelist
        holder.injected_env = dict(policy.get("injected_env", {}) or {})
        holder.policy_loaded = True
        logger.info(
            f"[Config] 沙箱策略已加载: allow_network={holder.allow_network}, "
            f"hosts={len(holder.allowed_hosts)}, write_paths={len(holder.allowed_write_paths)}"
        )
    except ImportError:
        logger.warning("[Config] 未安装 pyyaml，沙箱策略使用内置默认值（默认拒绝）")
        holder.allow_network = False
        holder.policy_loaded = True
    except Exception as e:
        logger.error(f"[Config] 沙箱策略加载失败: {e}，启用默认拒绝基线")
        holder.allow_network = False
        holder.policy_loaded = True
    return holder


sandbox_config = SandboxConfigHolder.from_env()
load_sandbox_policy(sandbox_config)
