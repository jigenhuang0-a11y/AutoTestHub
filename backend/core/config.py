"""
Agent 编排底座 - 统一配置中心
============================
所有 AI 相关配置集中管理，支持环境变量 + 默认值。
"""
import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ModelConfig:
    """单个模型的配置"""
    name: str              # 模型名，如 qwen-max
    provider: str          # 所属 Provider: dashscope / deepseek / glm
    capabilities: list     # 能力标签: reasoning / coding / fast / multimodal / embedding
    max_tokens: int = 4096
    temperature: float = 0.7
    priority: int = 1      # 优先级（越大越优先）


@dataclass
class LLMRouterConfig:
    """LLM 路由配置 — 按任务类型自动选模型"""
    
    # 任务 → 推荐模型列表（按优先级排序）
    route_map: dict = field(default_factory=lambda: {
        "planning":          ["deepseek-chat", "qwen-max"],       # 复杂规划/推理
        "code_generation":   ["deepseek-chat", "qwen-plus"],     # 代码生成
        "evaluation":        ["deepseek-chat", "qwen-max"],      # 质量评估
        "fast_chat":         ["qwen-turbo", "glm-4-flash"],     # 快速对话
        "embedding":         ["text-embedding-v3"],               # 向量化（仅千问支持）
        "data_generation":   ["deepseek-chat", "qwen-plus"],     # 数据构造
        "rag_query":         ["qwen-plus", "qwen-turbo"],        # RAG 问答
        "fallback":          ["qwen-turbo"],                      # 降级兜底
        "generation":        ["deepseek-chat", "qwen-plus"],     # 用例/数据生成
    })
    
    # 默认模型（所有任务兜底）
    default_model: str = "deepseek-chat"
    
    def get_model(self, task_type: str, available_providers: set) -> str:
        """根据任务类型返回最佳可用模型"""
        candidates = self.route_map.get(task_type, [self.default_model])
        for model in candidates:
            provider = _get_provider_name(model)
            if provider in available_providers:
                return model
        return self.default_model


@dataclass
class AgentConfig:
    """Agent 编排配置"""
    
    # LangGraph 配置
    max_retries: int = 3             # 最大重试次数
    max_steps: int = 20              # 工作流最大步数
    timeout_seconds: int = 300       # 单个 Agent 超时
    
    # 并发配置
    max_concurrent_agents: int = 3   # 最大并行 Agent 数
    
    # 记忆/状态
    session_ttl_seconds: int = 3600  # 会话状态过期时间


@dataclass
class VectorStoreConfig:
    """向量数据库配置"""
    
    # Milvus 配置
    milvus_host: str = "localhost"
    milvus_port: int = 19530
    milvus_collection_name: str = "ai_test_knowledge"
    milvus_dim: int = 1024          # text-embedding-v3 维度
    
    # ChromaDB 降级配置
    chroma_persist_dir: str = ""
    use_chroma_fallback: bool = True
    
    # 检索配置
    default_top_k: int = 5
    similarity_threshold: float = 0.7


# ============================================================
# 可用模型注册表
# ============================================================
MODEL_REGISTRY: dict[str, ModelConfig] = {
    # DashScope 千问系列
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
    "text-embedding-v3": ModelConfig(
        name="text-embedding-v3", provider="dashscope",
        capabilities=["embedding"],
        max_tokens=0, temperature=0, priority=3,
    ),
    
    # DeepSeek 系列
    "deepseek-chat": ModelConfig(
        name="deepseek-chat", provider="deepseek",
        capabilities=["reasoning", "code_generation", "planning", "evaluation"],
        max_tokens=8192, temperature=0.3, priority=3,
    ),
    
    # 智谱 GLM 系列
    "glm-4-flash": ModelConfig(
        name="glm-4-flash", provider="glm",
        capabilities=["fast_chat", "code_generation"],
        max_tokens=4096, temperature=0.7, priority=1,
    ),
}


def _get_provider_name(model_name: str) -> str:
    """从模型名推断 Provider 名"""
    if model_name in MODEL_REGISTRY:
        return MODEL_REGISTRY[model_name].provider
    # 简化推断
    if model_name.startswith("qwen") or model_name.startswith("text-embedding"):
        return "dashscope"
    if model_name.startswith("deepseek"):
        return "deepseek"
    if model_name.startswith("glm"):
        return "glm"
    return "dashscope"


def get_available_providers() -> set:
    """检查哪些 Provider 的 API Key 已配置"""
    from django.conf import settings
    available = set()
    if getattr(settings, 'DASHSCOPE_API_KEY', ''):
        available.add('dashscope')
    if getattr(settings, 'DEEPSEEK_API_KEY', ''):
        available.add('deepseek')
    if getattr(settings, 'GLM_API_KEY', ''):
        available.add('glm')
    return available


# ============================================================
# 从环境变量加载配置
# ============================================================
def load_config() -> tuple[LLMRouterConfig, AgentConfig, VectorStoreConfig]:
    """从环境变量加载所有配置"""
    router = LLMRouterConfig()
    agent = AgentConfig()
    vector = VectorStoreConfig(
        milvus_host=os.getenv('MILVUS_HOST', 'localhost'),
        milvus_port=int(os.getenv('MILVUS_PORT', '19530')),
    )
    return router, agent, vector
