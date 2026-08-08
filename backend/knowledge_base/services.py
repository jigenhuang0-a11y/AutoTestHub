"""
RAG 引擎 — 企业级向量检索 (Milvus)

支持：
- 亿级文档向量化存储
- 毫秒级高并发检索
- 多知识库隔离 (Partition / filter)
- 流式问答输出
- LLM: DeepSeek Chat（OpenAI 兼容接口）
- Embedding: 本地模型 sentence-transformers（无 API 依赖）

依赖:
    pymilvus>=2.4.0  (企业级向量数据库)
    sentence-transformers  (本地向量化)
"""
import os
import json
import logging
import time
import hashlib
from pathlib import Path
from django.conf import settings

# Embedding & LLM
from langchain_openai import ChatOpenAI
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_community.document_loaders import PyPDFLoader, TextLoader

from core.harness_client import harness_chat, harness_chat_stream

import docx2txt
from langchain_core.documents import Document
import requests

logger = logging.getLogger(__name__)

# ---------- Embedding 模型 (DashScope API, 1024维) ----------
class DashScopeEmbeddings:
    """使用 DashScope text-embedding-v3 API"""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv('DASHSCOPE_API_KEY')
        self.api_url = "https://dashscope.aliyuncs.com/api/v1/services/embeddings/text-embedding/text-embedding"
        self.model = "text-embedding-v3"
        self.embedding_dim = 1024
        if not self.api_key:
            raise ValueError("DASHSCOPE_API_KEY 未设置")

    def _call_api(self, texts: list) -> list:
        """调用 DashScope Embedding API，返回向量列表"""
        import requests
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        # 过滤空文本
        valid_texts = [t for t in texts if t and t.strip()]
        if not valid_texts:
            return [[0.0] * self.embedding_dim] * len(texts)

        payload = {
            "model": self.model,
            "input": {
                "texts": valid_texts
            }
        }
        resp = requests.post(self.api_url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        embeddings = data.get("output", {}).get("embeddings", [])
        if not embeddings:
            raise ValueError(f"DashScope API 返回空 embeddings: {data}")
        # 按 index 排序返回向量
        vectors = [emb["embedding"] for emb in sorted(embeddings, key=lambda x: x["text_index"])]
        return vectors

    def embed_query(self, text: str):
        return self._call_api([text])[0]

    def embed_documents(self, texts: list):
        return self._call_api(texts)


# 兼容旧接口
_get_embedding_model = None


# ---------- 本地 Embedding 模型（隐私优先）----------
class LocalEmbeddings:
    """
    使用本地 sentence-transformers 模型做 Embedding

    无需 API Key，数据不出本地。
    默认使用 bge-large-zh-v1.5（1024 维，与 DashScope text-embedding-v3 兼容）。

    模型大小参考:
        bge-large-zh-v1.5  → 1024维, ~1.3GB（推荐，与现有 Milvus 兼容）
        bge-m3             → 1024维, ~2.4GB（多语言）
        bge-small-zh-v1.5  → 512维,  ~130MB（需重建 Milvus Collection）
    """

    def __init__(self, model_name: str = None, device: str = "cpu"):
        from django.conf import settings
        model_name = model_name or getattr(settings, 'LOCAL_EMBEDDING_MODEL', 'BAAI/bge-large-zh-v1.5')
        self.model_name = model_name

        # 使用 sentence_transformers（比 langchain_community 的 HuggingFaceEmbeddings 更可靠）
        from sentence_transformers import SentenceTransformer
        logger.info(f"[RAG] 加载本地 Embedding 模型: {model_name} (device={device})")
        self._model = SentenceTransformer(model_name, device=device)
        self.embedding_dim = self._model.get_sentence_embedding_dimension()
        logger.info(f"[RAG] 本地 Embedding 维度: {self.embedding_dim}")

    def embed_query(self, text: str):
        return self._model.encode(text, normalize_embeddings=True).tolist()

    def embed_documents(self, texts: list):
        return self._model.encode(texts, normalize_embeddings=True).tolist()


def get_embedding_model() -> object:
    """
    Embedding 模型工厂函数

    优先级: 本地模型 > DashScope API

    - USE_LOCAL_EMBEDDING=true  → 使用 sentence-transformers（无 API Key，数据不出本地）
    - USE_LOCAL_EMBEDDING=false → 使用 DashScope text-embedding-v3（需 API Key）

    注意: 本地模型维度必须与 Milvus Collection 匹配（当前为 1024 维）。
          切换模型维度后需要重建 Collection。
    """
    from django.conf import settings

    use_local = getattr(settings, 'USE_LOCAL_EMBEDDING', False)

    if use_local:
        try:
            model = LocalEmbeddings()
            logger.info(f"[RAG] 使用本地 Embedding: {model.model_name} ({model.embedding_dim}维)")
            return model
        except Exception as e:
            logger.warning(f"[RAG] 本地 Embedding 不可用 ({e})，降级到 DashScope")

    # DashScope 作为 fallback
    return DashScopeEmbeddings()



class RAGEngine:
    """
    基于 Milvus 的企业级 RAG 引擎

    架构:
        文档 → 分块(Chunking) → 本地 Embedding → Milvus 存储
                                              ↓
        用户查询 → Embedding → Milvus 检索 Top-K → DeepSeek 生成答案
    """

    # 支持图片输入的模型名称关键字（小写）
    VISION_MODEL_KEYWORDS = {
        'qwen-vl', 'gpt-4o', 'gpt-4-turbo', 'claude-3', 'gemini', 'llava',
        'vision', 'multimodal', 'yi-vision', 'glm-4v'
    }

    @classmethod
    def _check_vision_support(cls, model_id: str) -> bool:
        """根据模型名称判断是否支持图片输入"""
        if not model_id:
            return False
        model_lower = model_id.lower()
        return any(kw in model_lower for kw in cls.VISION_MODEL_KEYWORDS)

    def __init__(self):
        # ---------- 从数据库读取 LLM 配置 ----------
        import django
        try:
            django.setup()
        except RuntimeError:
            pass

        from ai_evaluator.models import AIModelConfig
        from django.conf import settings as django_settings

        # 策略 1: 本地 Ollama 优先（隐私优先）
        ollama_url = getattr(django_settings, 'OLLAMA_BASE_URL', '')
        if ollama_url:
            self.api_key = "ollama"  # Ollama 不需要真实 API Key
            self.api_url = ollama_url
            self.model_id = getattr(django_settings, 'OLLAMA_MODEL', 'qwen2.5:7b')
            logger.info(f"[RAG] 使用本地 Ollama: {self.model_id} @ {ollama_url}")
        else:
            # 策略 2: 数据库中的远程模型配置
            ds_config = AIModelConfig.objects.filter(
                is_active=True, model_id='deepseek-chat'
            ).first()
            if not ds_config or not ds_config.api_key:
                ds_config = AIModelConfig.objects.filter(is_active=True).first()
            if not ds_config or not ds_config.api_key:
                raise ValueError("没有可用的 LLM 模型配置，请配置数据库或设置 OLLAMA_BASE_URL")
            self.api_key = ds_config.api_key
            self.api_url = ds_config.api_url or "https://api.deepseek.com/v1"
            self.model_id = ds_config.model_id or "deepseek-chat"
            logger.info(f"[RAG] 使用远程 LLM: {self.model_id} @ {self.api_url}")

        # ---------- Embedding 模型（本地优先，DashScope 降级）----------
        self.embeddings = get_embedding_model()

        # ---------- LLM (OpenAI 兼容接口) ----------
        base_url = self.api_url.rstrip('/')
        if base_url.endswith('/chat/completions'):
            base_url = base_url[:-len('/chat/completions')]
        if not base_url.endswith('/'):
            base_url += '/'

        self.llm = ChatOpenAI(
            model=self.model_id,
            openai_api_key=self.api_key,
            openai_api_base=base_url,
            temperature=0.7,
            max_tokens=2000,
        )

        # 多模态能力检测
        self.supports_vision = self._check_vision_support(self.model_id)
        self.llm_vision = self.llm

        # ---------- 文本分割器 ----------
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50,
            separators=["\n\n", "\n", " ", ""],
        )

        # ---------- Milvus Store (延迟初始化) ----------
        self._store = None

    @property
    def store(self):
        """延迟初始化 Milvus 向量存储"""
        if self._store is None:
            try:
                from core.tools.milvus_store import get_milvus_store
                self._store = get_milvus_store()
            except Exception as e:
                logger.warning(f"[RAG] Milvus 不可用 ({e})，知识库检索将降级为纯 LLM 对话")
                self._store = None
        return self._store

    @property
    def milvus_available(self) -> bool:
        """检查 Milvus 向量存储是否真正可用（包含连接测试）"""
        if self._store is False:
            return False
        try:
            s = self.store
            if s is None:
                return False
            # 真正测试连接，不只是检查对象存在
            result = s.health_check()
            return result.get("status") == "ok"
        except Exception:
            self._store = False
            return False

    # ================================================================
    # 文档处理: 上传 → 分块 → 向量化 → 入库
    # ================================================================

    def process_document(self, file_path: str, knowledge_base_id: int) -> int:
        """
        处理文档：加载 → 分块 → 嵌入 → 存入 Milvus
        
        Returns:
            分块数量
        """
        start = time.time()
        
        if not self.milvus_available:
            raise Exception("Milvus 向量数据库未启动，无法处理文档。请管理员启动 Milvus 服务。")
        
        try:
            # 1. 加载文档
            documents = self._load_document(file_path)

            # 2. 添加元数据
            for doc in documents:
                doc.metadata['knowledge_base_id'] = knowledge_base_id

            # 3. 分块
            chunks = self.text_splitter.split_documents(documents)

            if not chunks:
                logger.warning(f"[RAG] 文档 {file_path} 分块结果为空")
                return 0

            # 4. 生成向量 ID 和嵌入
            ids = []
            vectors = []
            contents = []
            kb_ids = []
            chunk_indices = []

            for idx, chunk in enumerate(chunks):
                # 唯一 ID: kb_{kb_id}_doc_{hash}_chunk_{idx}
                content_hash = hashlib.md5(chunk.page_content.encode()).hexdigest()[:12]
                unique_id = f"kb_{knowledge_base_id}_{content_hash}_{idx}"
                
                ids.append(unique_id)
                contents.append(chunk.page_content)
                kb_ids.append(knowledge_base_id)
                chunk_indices.append(idx)

            # 批量嵌入：分批次处理，避免 DashScope API 单次请求限制（text-embedding-v3 上限 10 条）
            batch_size = 10
            vectors = []
            for i in range(0, len(contents), batch_size):
                batch = contents[i:i + batch_size]
                batch_vectors = self.embeddings.embed_documents(batch)
                vectors.extend(batch_vectors)

            # 5. 批量写入 Milvus
            result = self.store.upsert(
                ids=ids,
                vectors=vectors,
                contents=contents,
                kb_ids=kb_ids,
                chunk_indices=chunk_indices,
            )

            duration = time.time() - start
            logger.info(f"[RAG] 文档处理完成: kb_id={knowledge_base_id}, chunks={len(chunks)}, "
                       f"耗时={duration:.2f}s")

            return len(chunks)

        except Exception as e:
            logger.exception(f"[RAG] 文档处理失败: {e}")
            raise Exception(f"文档处理失败: {str(e)}")

    def _load_document(self, file_path: str) -> list[Document]:
        """根据文件类型加载文档"""
        ext = Path(file_path).suffix.lower()

        if ext == '.pdf':
            loader = PyPDFLoader(file_path)
            return loader.load()

        elif ext == '.docx':
            text = docx2txt.process(file_path)
            return [Document(page_content=text, metadata={'source': file_path})]

        elif ext == '.txt':
            loader = TextLoader(file_path, encoding='utf-8')
            return loader.load()

        else:
            raise ValueError(f"不支持的文件类型: {ext}")

    # ================================================================
    # 知识库问答 (非流式)
    # ================================================================

    def answer_question(self, question: str, knowledge_base_id: int,
                        system_prompt: str = None, images: list = None) -> dict:
        """
        基于知识库回答问题（支持多模态图片输入）
        
        Args:
            question: 用户问题
            knowledge_base_id: 知识库 ID
            system_prompt: 可选自定义 system prompt
            images: 可选 base64 图片列表
            
        Returns:
            {"answer": "...", "context_docs": [...]}
        """
        try:
            # 0. Milvus 可用性检查
            if not self.milvus_available:
                logger.warning(f"[RAG] 向量存储不可用，无法基于知识库回答")
                return {
                    'answer': '知识库检索服务暂不可用，无法基于知识库回答。请检查 Milvus 向量数据库是否正常运行后重试。',
                    'context_docs': []
                }

            # 1. 查询向量化
            query_vector = self.embeddings.embed_query(question)

            # 2. Milvus 检索 Top-5（相似度阈值 0.2，过滤低质量匹配）
            hits = self.store.search(
                query_vector=query_vector,
                top_k=5,
                kb_id=knowledge_base_id,
                similarity_threshold=0.2,
            )
            logger.info(f"[answer_question] hits={len(hits)}, "
                        f"scores={[h.get('score','N/A') for h in hits]}")

            # 3. 未命中知识库 → 自动降级为日常对话（RAG + 通用问答融合）
            if not hits:
                logger.info(f"[RAG] 知识库 #{knowledge_base_id} 未命中相关内容，"
                            f"问题将交由通用对话能力回答")
                return self.chat(question, system_prompt=system_prompt, images=images)

            # 3. 构建 Prompt 上下文
            context_parts = [f"文档片段 {i+1}:\n{hit['content']}" for i, hit in enumerate(hits)]
            context = "\n\n".join(context_parts)

            # 4. System Prompt — 知识库模式下只用强约束，不引入角色设定干扰
            # 支持图片时，允许模型结合图片理解用户问题
            vision_images = images if (images and self.supports_vision) else None
            if images and not self.supports_vision:
                logger.warning(f"[RAG] 当前模型 {self.model_id} 不支持图片输入，已忽略图片")

            image_hint = "\n5. 如果用户提供了图片，请结合图片内容理解问题，但回答仍只能基于【知识库内容】。" if vision_images else ""
            final_system_prompt = (
                "你是「知识库问答助手」。你的唯一任务是根据下面提供的「知识库内容」回答用户问题。\n"
                "【绝对规则】\n"
                "1. 你只能使用「知识库内容」中的信息回答，禁止使用通用知识、训练数据、常识或外部信息。\n"
                "2. 如果「知识库内容」中没有直接包含用户问题的答案，你必须只回复：「知识库中没有相关信息。」\n"
                "3. 禁止编造、推测、扩展、总结知识库中没有的信息。\n"
                "4. 优先使用知识库中的原文，保持准确、简洁。"
                f"{image_hint}\n"
                "违反以上规则会产生错误回答。"
            )

            user_prompt = f"""请根据以下「知识库内容」回答用户问题。

【知识库内容】
{context}

【用户问题】
{question}

【回答要求 - 必须遵守】
- 只能使用【知识库内容】中的信息回答。
- 如果【知识库内容】中没有直接包含该问题的答案，请只回复：「知识库中没有相关信息。」，不要输出任何其他内容。
- 禁止使用通用知识、训练数据、常识或外部信息。
- 禁止编造、推测、扩展知识库中没有的信息。"""

            # 5. 组装消息：支持多模态图片输入
            user_content = [{"type": "text", "text": user_prompt}]
            if vision_images:
                for img_b64 in vision_images:
                    user_content.append({"type": "image", "image": img_b64})

            messages = [
                SystemMessage(content=final_system_prompt),
                HumanMessage(content=user_content),
            ]
            answer = self._invoke_llm(messages)
            answer = self._extract_text(answer)

            # 如果模型不支持图片但用户传了图片，追加提示
            if images and not self.supports_vision:
                answer = f"[当前模型 {self.model_id} 不支持图片输入，已忽略图片]\n\n{answer}"

            context_docs = [
                {
                    'content': hit['content'][:200] + ('...' if len(hit['content']) > 200 else ''),
                    'metadata': {
                        **hit['metadata'],
                        'score': round(hit['score'], 4),
                    },
                }
                for hit in hits
            ]

            return {'answer': answer, 'context_docs': context_docs}

        except Exception as e:
            logger.exception(f"[RAG] 问答失败: {e}")
            raise Exception(f"问答失败: {str(e)}")

    # ================================================================
    # 知识库问答 (流式 SSE)
    # ================================================================

    def answer_question_stream(self, question: str, knowledge_base_id: int, system_prompt: str = None,
                                enable_reasoning: bool = False, images: list = None):
        """
        基于知识库回答 — 流式输出（yield dict: {'type':'token'|'status','content':str}）
        
        用于 SSE 接口（Milvus 不可用时降级为纯 LLM 对话流）
        
        Args:
            enable_reasoning: 是否启用深度思考（先推理再回答）
            images: 可选 base64 图片列表，支持多模态问答
        """
        # 1. 先给用户一个即时反馈，避免长时间空白
        yield {'type': 'status', 'content': '正在分析问题意图...'}

        # 2. Milvus 可用性检查
        if not self.milvus_available:
            logger.warning(f"[RAG] 向量存储不可用，无法基于知识库回答")
            yield {'type': 'status', 'content': '知识库检索服务暂不可用'}
            yield {'type': 'token', 'content': '知识库检索服务暂不可用，无法基于知识库回答。请检查 Milvus 向量数据库是否正常运行后重试。'}
            return

        # 3. 向量化查询
        yield {'type': 'status', 'content': '正在将问题转换为向量表示...'}
        query_vector = self.embeddings.embed_query(question)

        # 4. 检索知识库（相似度阈值 0.2，过滤低质量匹配）
        yield {'type': 'status', 'content': '正在知识库中检索相关文档...'}
        hits = self.store.search(
            query_vector=query_vector,
            top_k=5,
            kb_id=knowledge_base_id,
            similarity_threshold=0.2,
        )
        logger.info(f"[answer_question_stream] hits={len(hits)}, "
                    f"scores={[h.get('score','N/A') for h in hits]}")

        # 5. 未命中知识库 → 自动降级为日常对话流（RAG + 通用问答融合）
        if not hits:
            logger.info(f"[RAG] 知识库 #{knowledge_base_id} 未命中相关内容，"
                        f"流式回答降级为通用对话")
            yield {'type': 'status', 'content': '未检索到相关文档，将基于通用能力回答'}
            yield from self.chat_stream(
                question,
                system_prompt=system_prompt,
                enable_reasoning=enable_reasoning,
                images=images,
            )
            return

        # 5. 显示检索结果摘要
        doc_scores = [f"{h.get('score', 0):.2f}" for h in hits[:3]]
        yield {'type': 'status', 'content': f'已筛选 {len(hits)} 条相关文档（相关度: {", ".join(doc_scores)}）'}

        # 6. 构建上下文
        yield {'type': 'status', 'content': '正在组织上下文并构建提示词...'}
        context = "\n\n".join([f"文档片段 {i+1}:\n{hit['content']}" for i, hit in enumerate(hits)])

        # 严格约束：只能基于检索到的知识库内容回答，禁止依赖通用知识
        # 图片能力检测
        vision_images = images if (images and self.supports_vision) else None
        if images and not self.supports_vision:
            logger.warning(f"[RAG] 当前模型 {self.model_id} 不支持图片输入，已忽略图片")

        # 支持图片时，允许模型结合图片内容理解问题
        image_hint = "\n5. 如果用户提供了图片，请结合图片内容理解问题，但回答仍只能基于【知识库内容】。" if vision_images else ""
        base_instruction = (
            "你是「知识库问答助手」。你的唯一任务是根据下面提供的「知识库内容」回答用户问题。\n"
            "【绝对规则】\n"
            "1. 你只能使用「知识库内容」中的信息回答，禁止使用通用知识、训练数据、常识或外部信息。\n"
            "2. 如果「知识库内容」中没有直接包含用户问题的答案，你必须只回复：「知识库中没有相关信息。」\n"
            "3. 禁止编造、推测、扩展、总结知识库中没有的信息。\n"
            "4. 优先使用知识库中的原文，保持准确、简洁。"
            f"{image_hint}\n"
            "违反以上规则会产生错误回答。"
        )

        # 知识库模式下不使用角色设定，只用强约束以保证答案严格基于知识库
        final_system_prompt = base_instruction

        user_prompt = f"""请根据以下「知识库内容」回答用户问题。

【知识库内容】
{context}

【用户问题】
{question}

【回答要求 - 必须遵守】
- 只能使用【知识库内容】中的信息回答。
- 如果【知识库内容】中没有直接包含该问题的答案，请只回复：「知识库中没有相关信息。」，不要输出任何其他内容。
- 禁止使用通用知识、训练数据、常识或外部信息。
- 禁止编造、推测、扩展知识库中没有的信息。"""

        # 7. 组装消息：支持多模态图片输入
        user_content = [{"type": "text", "text": user_prompt}]
        if vision_images:
            for img_b64 in vision_images:
                user_content.append({"type": "image", "image": img_b64})

        messages = [
            {"role": "system", "content": final_system_prompt},
            {"role": "user", "content": user_content},
        ]

        # 调试：打印最终发送给 LLM 的消息
        logger.info(f"[answer_question_stream] messages={json.dumps(messages, ensure_ascii=False)[:1000]}")

        # 8. 链式推理流式调用 LLM（先深度推理、后给出答案）
        # 注意：如果携带图片，深度思考阶段会丢失图片，因此有图片时直接回答
        if vision_images:
            yield {'type': 'status', 'content': '正在生成回答...'}
            for token in self._stream_llm(messages, max_tokens=2000):
                yield {'type': 'token', 'content': token}
            return

        # 如果模型不支持图片但用户传了图片，先提示再基于文本回答
        if images and not self.supports_vision:
            yield {'type': 'status', 'content': f'当前模型 {self.model_id} 不支持图片输入，已忽略图片'}

        yield from self._stream_chain_of_thought(messages, enable_reasoning=enable_reasoning)

    # ================================================================
    # 日常对话模式 (非知识库)
    # ================================================================

    def chat(self, question: str, system_prompt: str = None, images: list = None) -> dict:
        """通用对话 — 支持多模态（自动检测模型是否支持图片）"""
        try:
            final_system_prompt = system_prompt or (
                "你是一个智能AI助手，可以帮助用户解答各种问题、编写代码、分析数据等。\n"
                "请提供准确、有用且易于理解的帮助。"
            )

            vision_images = images if (images and self.supports_vision) else None
            if images and not self.supports_vision:
                logger.warning(f"[RAG] 当前模型 {self.model_id} 不支持图片输入，已忽略图片")

            content = [{"type": "text", "text": question}]
            if vision_images:
                for img_b64 in vision_images:
                    content.append({"type": "image", "image": img_b64})

            messages = [
                SystemMessage(content=final_system_prompt),
                HumanMessage(content=content),
            ]
            answer = self._invoke_llm(messages)
            answer = self._extract_text(answer)

            if images and not self.supports_vision:
                answer = f"[当前模型 {self.model_id} 不支持图片输入，已忽略图片]\n\n{answer}"

            return {'answer': answer, 'context_docs': []}
        except Exception as e:
            logger.exception(f"[RAG] 聊天失败: {e}")
            raise Exception(f"聊天失败: {str(e)}")

    def chat_stream(self, question: str, system_prompt: str = None, images: list = None,
                    enable_reasoning: bool = False):
        """对话模式 — 链式推理流式输出（先推理、后回答）
        
        Args:
            enable_reasoning: 是否启用深度思考（先推理再回答）
        """
        final_system_prompt = system_prompt or (
            "你是一个智能AI助手，可以帮助用户解答各种问题、编写代码、分析数据等。\n"
            "请提供准确、有用且易于理解的帮助。"
        )

        vision_images = images if (images and self.supports_vision) else None
        if images and not self.supports_vision:
            logger.warning(f"[RAG] 当前模型 {self.model_id} 不支持图片输入，已忽略图片")

        if vision_images:
            content = [{"type": "text", "text": question}]
            for img_b64 in vision_images:
                content.append({"type": "image", "image": img_b64})
        else:
            content = question

        messages = [
            {"role": "system", "content": final_system_prompt},
            {"role": "user", "content": content},
        ]

        # 如果模型不支持图片但用户传了图片，先提示再基于文本回答
        if images and not self.supports_vision:
            yield {'type': 'status', 'content': f'当前模型 {self.model_id} 不支持图片输入，已忽略图片'}

        # 链式推理：先让模型分析，再输出答案
        yield from self._stream_chain_of_thought(messages, enable_reasoning=enable_reasoning)

    # ================================================================
    # 删除操作
    # ================================================================

    def delete_knowledge_base_data(self, knowledge_base_id: int):
        """删除指定知识库在 Milvus 中的所有向量数据"""
        try:
            self.store.delete_by_kb_id(knowledge_base_id)
            logger.info(f"[RAG] 已删除知识库 #{knowledge_base_id} 的向量数据")
        except Exception as e:
            logger.error(f"[RAG] 删除知识库数据失败: {e}")
            raise Exception(f"删除知识库数据失败: {str(e)}")

    def delete_document_vectors(self, document_id: int):
        """删除指定文档在 Milvus 中的所有向量数据（文档删除时同步清理）"""
        try:
            self.store.delete_by_doc_id(document_id)
            logger.info(f"[RAG] 已删除文档 #{document_id} 的向量数据")
        except Exception as e:
            logger.error(f"[RAG] 删除文档向量失败: {e}")
            raise Exception(f"删除文档向量失败: {str(e)}")

    # ================================================================
    # 向量统计
    # ================================================================

    def get_kb_stats(self, knowledge_base_id: int) -> dict:
        """获取知识库的向量统计信息"""
        if not self.milvus_available:
            return {
                "milvus_available": False,
                "total_vectors": 0,
                "message": "Milvus 不可用",
            }
        try:
            stats = self.store.get_collection_stats(kb_id=knowledge_base_id)
            stats["milvus_available"] = True
            return stats
        except Exception as e:
            return {
                "milvus_available": False,
                "total_vectors": 0,
                "error": str(e),
            }

    def raw_vector_search(self, query: str, knowledge_base_id: int = None,
                          top_k: int = 10, similarity_threshold: float = 0.3) -> list:
        """
        原始向量检索（不经过 LLM 问答），返回检索结果列表。
        供前端搜索框 / Agent 知识检索工具直接调用。

        Args:
            query: 检索文本
            knowledge_base_id: 知识库 ID（None 则跨库搜索）
            top_k: 返回结果数
            similarity_threshold: 相似度阈值，低于此值的结果不返回

        Returns:
            [{"content": "...", "score": 0.95, "metadata": {...}}, ...]
        """
        if not self.milvus_available:
            return []

        query_vector = self.embeddings.embed_query(query)
        raw_results = self.store.search(
            query_vector=query_vector,
            top_k=top_k,
            kb_id=knowledge_base_id,
            similarity_threshold=similarity_threshold,
        )
        return raw_results

    # ================================================================
    # 内部工具方法
    # ================================================================

    @staticmethod
    def _extract_text(answer) -> str:
        """提取 LLM 回复中的纯文本（处理多模态返回格式）"""
        if isinstance(answer, list):
            parts = []
            for item in answer:
                if isinstance(item, dict) and 'text' in item:
                    parts.append(item['text'])
                elif isinstance(item, str):
                    parts.append(item)
            return '\n'.join(parts)
        elif isinstance(answer, str):
            return answer
        return str(answer)

    def _stream_deepseek(self, messages: list, model: str = None, max_tokens: int = 2000):
        """调用 DeepSeek API 实现流式输出（OpenAI 兼容格式）"""
        # api_url 已存储完整 endpoint，直接使用
        url = self.api_url
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }
        payload = {
            "model": model or self.model_id,
            "messages": messages,
            "stream": True,
            "stream_options": {"include_usage": True},
            "temperature": 0.7,
            "max_tokens": max_tokens,
        }

        response = requests.post(url, headers=headers, json=payload, stream=True, timeout=120)

        for line in response.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data:"):
                continue
            data_str = line[5:].strip()
            if data_str == "[DONE]":
                break
            try:
                data = json.loads(data_str)
                choices = data.get("choices", [])
                if choices:
                    delta = choices[0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        yield content
            except json.JSONDecodeError:
                continue

    def _stream_chain_of_thought(self, messages: list, max_tokens: int = 2000, 
                                  reasoning_max_tokens: int = 400,
                                  enable_reasoning: bool = False):
        """
        链式推理流式输出: 先深度推理 (reasoning)，再给出正式回答 (token)。
        
        Phase 1: 让模型独立分析问题 → 以 reasoning 事件流式输出
        Phase 2: 让模型基于分析生成答案 → 以 token 事件流式输出
        
        Args:
            enable_reasoning: 是否启用深度思考。为 False 时直接回答，减少一次 LLM 调用。
        """
        import re

        # 未启用深度思考时直接回答
        if not enable_reasoning:
            yield {'type': 'status', 'content': '正在生成回答...'}
            for token in self._stream_llm(messages, max_tokens=max_tokens):
                yield {'type': 'token', 'content': token}
            return

        # ---------- 提取用户问题和 system prompt ----------
        user_content = ''
        system_content = ''
        for msg in messages:
            role = msg.get('role', '')
            content = msg.get('content', '')
            if role == 'system':
                system_content = content
            elif role == 'user':
                if isinstance(content, str):
                    user_content = content
                elif isinstance(content, list):
                    for part in content:
                        if isinstance(part, dict) and part.get('type') == 'text':
                            user_content += part.get('text', '')

        # 尝试从包装后的消息中提取原始问题（知识库模式下问题被包装在模板中）
        raw_question = user_content
        for marker in ['用户问题', 'User question']:
            parts = user_content.split(marker)
            if len(parts) > 1:
                raw_question = parts[-1].strip()
                # 去掉冒号和换行
                raw_question = re.sub(r'^[：:]\s*\n*', '', raw_question)
                # 只取第一段（到下一个提示词前）
                raw_question = re.split(r'\n(?:请|Please|基于)', raw_question)[0].strip()
                break

        # ========================
        # Phase 1: 深度推理（独立 LLM 调用）
        # ========================
        yield {'type': 'status', 'content': '开始深度思考...'}

        think_system = (
            "你是一个善于深度推理的 AI 助手。请基于用户提供的资料（如有）和问题，"
            "一步步分析：资料中哪些信息与问题相关、如何组织答案、需要注意什么。"
            "只输出推理分析过程，不要给出最终答案。"
            "用要点式、简洁的输出格式，控制在 300 字以内。"
        )

        # 推理阶段使用完整 user_content（知识库模式下包含检索到的上下文）
        think_messages = [
            {"role": "system", "content": think_system},
            {"role": "user", "content": f"请基于以下资料进行深度分析：\n{user_content}"},
        ]

        reasoning_full = ''
        for token in self._stream_llm(think_messages, max_tokens=reasoning_max_tokens):
            reasoning_full += token
            yield {'type': 'reasoning', 'content': token}

        # ========================
        # Phase 2: 正式回答（带上推理上下文）
        # ========================
        yield {'type': 'status', 'content': '推理完成，正在生成正式答案...'}

        # 在原始 messages 的 user 消息中注入推理结果，帮助模型给出更一致的答案
        augmented_messages = []
        for msg in messages:
            role = msg.get('role', '')
            content = msg.get('content', '')
            if role == 'user':
                if isinstance(content, str):
                    augmented_messages.append({
                        "role": "user",
                        "content": f"{content}\n\n[推理分析]\n{reasoning_full}\n[/推理分析]"
                    })
                else:
                    augmented_messages.append(msg)
            else:
                augmented_messages.append(msg)

        for token in self._stream_llm(augmented_messages, max_tokens=max_tokens):
            yield {'type': 'token', 'content': token}

    def _invoke_llm(self, messages: list, model_name: str = None) -> str:
        """优先调用 Agent Harness，失败降级到本地 LLM。"""
        try:
            answer = harness_chat(messages, model=model_name or self.model_id, task_type="knowledge_base")
            if answer:
                return answer
        except Exception as e:
            logger.warning(f"[RAG] Harness 调用失败，将降级: {e}")
        logger.info("[RAG] Harness 不可用，降级到本地 LLM")
        response = self.llm.invoke(messages)
        return self._extract_text(response)

    def _stream_llm(self, messages: list, model_name: str = None, max_tokens: int = 2000):
        """优先调用 Agent Harness 流式接口，失败降级到本地 LLM 流式。"""
        try:
            stream_iter = harness_chat_stream(
                messages,
                model=model_name or self.model_id,
                task_type="knowledge_base",
                max_tokens=max_tokens,
            )
            first = next(stream_iter, None)
            if first == "":
                logger.info("[RAG] Harness stream 不可用，降级到本地 LLM")
                for chunk in self._stream_deepseek(messages, model=model_name, max_tokens=max_tokens):
                    yield chunk
                return
            if first is not None:
                yield first
            for chunk in stream_iter:
                yield chunk
            return
        except Exception as e:
            logger.warning(f"[RAG] Harness stream 调用失败，将降级: {e}")
        logger.info("[RAG] Harness stream 不可用，降级到本地 LLM")
        for chunk in self._stream_deepseek(messages, model=model_name, max_tokens=max_tokens):
            yield chunk
