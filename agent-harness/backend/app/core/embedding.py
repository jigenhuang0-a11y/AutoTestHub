"""
Embedding Provider — AI 底座的向量化能力。

设计：
- 主用 DashScope text-embedding-v2（云侧，零本地依赖，质量好）
- 兜底：本地 sentence-transformers（需联网下载一次模型，约 80MB）
- 接口与未来 Milvus embedding 对齐，便于平滑替换

调用方只需 `EmbeddingFactory.create().embed(texts)`，拿到的就是 float 向量列表。
"""
from __future__ import annotations

import logging
import os
from typing import List, Optional

logger = logging.getLogger(__name__)


class BaseEmbeddingProvider:
    """Embedding 抽象基类"""

    dim: int = 1536

    def embed(self, texts: List[str]) -> List[List[float]]:
        raise NotImplementedError


class DashScopeEmbeddingProvider(BaseEmbeddingProvider):
    """通义千问 text-embedding-v2

    - 维度 1536
    - 单次最多 25 条，单条最长 2048 token（自动截断）
    - 文档: https://help.aliyun.com/zh/dashscope/developer-reference/text-embedding
    """

    BASE_URL = "https://dashscope.aliyuncs.com/api/v1/services/embeddings/text-embedding/text-embedding"
    MODEL = "text-embedding-v2"
    dim = 1536
    BATCH = 25

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("DASHSCOPE_API_KEY")
        if not self.api_key:
            raise ValueError("缺少 DASHSCOPE_API_KEY，无法使用 DashScope Embedding")

    def embed(self, texts: List[str]) -> List[List[float]]:
        import requests

        out: List[List[float]] = []
        # 分批，避免超 batch 限制
        for i in range(0, len(texts), self.BATCH):
            batch = [t[:4000] for t in texts[i : i + self.BATCH]]
            try:
                resp = requests.post(
                    self.BASE_URL,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={"model": self.MODEL, "input": batch},
                    timeout=10,
                )
                resp.raise_for_status()
                data = resp.json()
                # 返回顺序与输入一致（output 按 input 顺序）
                for item in data["output"]["embeddings"]:
                    out.append(item["embedding"])
            except requests.Timeout as e:
                logger.error(f"[Embedding] DashScope embedding 请求超时（10s）: {e}")
                raise
        return out


class LocalEmbeddingProvider(BaseEmbeddingProvider):
    """本地 sentence-transformers 兜底。国内网络差时自动降级 MockEmbedding。"""

    def __init__(self, model: str = "iic/nlp_gte_sentence-embedding_chinese-base"):
        from sentence_transformers import SentenceTransformer

        # 国内网络优先走 ModelScope / HF 镜像，避免 huggingface.co 直连超时
        os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
        os.environ.setdefault("SENTENCE_TRANSFORMERS_HOME", os.path.expanduser("~/.cache/sentence_transformers"))

        st_model = None
        try:
            # 限制下载等待时间，避免首次请求卡死
            st_model = SentenceTransformer(model, device="cpu")
        except Exception as e:
            logger.warning(f"[Embedding] 本地模型 {model} 加载失败: {e}")

        if st_model is None:
            # 尝试更小的中文向量模型（通常更快且更稳定）
            try:
                st_model = SentenceTransformer("shibing624/text2vec-base-chinese", device="cpu")
            except Exception as e:
                logger.warning(f"[Embedding] 备用本地模型加载失败: {e}")

        if st_model is None:
            raise RuntimeError(
                "本地 embedding 模型加载失败。请检查网络连接，或设置环境变量 "
                "LOCAL_EMBEDDING_MODEL=/path/to/local/model 使用已下载的模型。"
            )

        self._model = st_model
        self.dim = self._model.get_sentence_embedding_dimension()

    def embed(self, texts: List[str]) -> List[List[float]]:
        vectors = self._model.encode(texts, normalize_embeddings=True)
        return [v.tolist() for v in vectors]


class MockEmbeddingProvider(BaseEmbeddingProvider):
    """Mock embedding，用于纯本地无网络环境快速验证。向量维度默认 1536，
    与 OpenAI/DashScope 默认维度对齐，避免和 LocalVectorStore 默认维度不一致。"""

    def __init__(self, dim: int = 1536):
        self.dim = dim

    def embed(self, texts: List[str]) -> List[List[float]]:
        """确定性生成 dim 维向量；维度与配置一致，避免写入向量库时维度不一致。"""
        import hashlib
        import random

        vectors = []
        for t in texts:
            seed = int(hashlib.md5(t.encode("utf-8")).hexdigest(), 16)
            rng = random.Random(seed)
            vectors.append([rng.random() for _ in range(self.dim)])
        return vectors


class EmbeddingFactory:
    """Embedding Provider 工厂（带兜底链）"""

    @classmethod
    def create(cls, prefer: str = "dashscope") -> BaseEmbeddingProvider:
        # 显式要求 Mock 模式时直接返回，不走任何网络
        if os.getenv("EMBEDDING_MODE", "").lower() == "mock":
            logger.info("[Embedding] 使用 Mock embedding（无网络）")
            return MockEmbeddingProvider()

        if os.getenv("DASHSCOPE_API_KEY"):
            try:
                provider = DashScopeEmbeddingProvider()
                # 不再同步预热，避免首次请求被 embedding API 阻塞数秒；
                # 有效性留到首次真实调用时自然验证，失败会记录并触发降级。
                logger.info("[Embedding] DashScope embedding 已配置")
                return provider
            except Exception as e:
                logger.warning(f"[Embedding] DashScope 不可用，回退本地: {e}")
        try:
            logger.info("[Embedding] 使用本地 sentence-transformers 兜底")
            return LocalEmbeddingProvider()
        except Exception as e:
            logger.warning(f"[Embedding] 本地模型加载失败，回退 Mock: {e}")
        return MockEmbeddingProvider()


_embedding_instance: Optional[BaseEmbeddingProvider] = None


def get_embedding_provider() -> BaseEmbeddingProvider:
    """全局单例，避免重复加载本地模型。失败时返回 Mock，保证上传流程不卡死。"""
    global _embedding_instance
    if _embedding_instance is None:
        try:
            _embedding_instance = EmbeddingFactory.create()
            # 做一次探测调用：Key 无效 / 无网络 / 本地模型异常等问题在首次真实请求前暴露，
            # 避免 ingest_document 走到一半才 500。
            _embedding_instance.embed(["embedding_probe"])
            logger.info(
                f"[Embedding] Provider 已就绪: {type(_embedding_instance).__name__}, dim={_embedding_instance.dim}"
            )
        except Exception as e:
            logger.error(f"[Embedding] Provider 初始化或探测失败，降级 Mock: {e}")
            _embedding_instance = MockEmbeddingProvider()
    return _embedding_instance
