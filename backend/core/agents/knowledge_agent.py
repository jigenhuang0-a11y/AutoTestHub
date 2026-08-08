"""
KnowledgeAgent — 知识库 RAG Agent

将 RAGEngine 封装为继承 BaseAgent 的标准 Agent，
使知识检索成为 Agent 流水线的一环。
"""
import logging
from typing import Optional

from core.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class KnowledgeAgent(BaseAgent):
    """
    知识库 RAG Agent — 基于 Milvus 的企业级向量检索
    
    能力：
    - 文档上传、分块、向量化、入库
    - 语义检索（Top-K 相似文档召回）
    - 知识问答（检索 + LLM 生成）
    - 知识库管理（增删查）
    
    对接 Harness 工作流：
        Plan("检索用户登录文档") → Orchestrate(name="knowledge") → KnowledgeAgent.run()
    """

    name = "KnowledgeAgent"
    description = "基于 Milvus 的企业级知识库 RAG Agent"
    task_type = "evaluation"  # 需要较长上下文的模型

    system_prompt = """你是一个专业的软件测试知识助手。
你的知识来自已上传的测试文档、接口规范和历史测试报告。
请基于知识库内容准确回答问题，如果知识库中没有相关信息，请如实说明。"""

    def __init__(self, knowledge_base_id: Optional[int] = None, **kwargs):
        super().__init__(**kwargs)
        self._engine = None
        self.knowledge_base_id = knowledge_base_id

    @property
    def engine(self):
        """延迟初始化 RAGEngine"""
        if self._engine is None:
            from knowledge_base.services import RAGEngine
            self._engine = RAGEngine()
        return self._engine

    def run(self, prompt: str, context: Optional[dict] = None) -> dict:
        """
        执行知识库检索

        模式:
        1. 如果 context 中有 kb_id → 知识库问答模式
        2. 如果 context 中有 file_path → 文档入库模式
        3. 否则 → 通用 LLM 问答模式

        Args:
            prompt: 用户问题/指令
            context: {"kb_id": int} 或 {"file_path": str, "kb_id": int} 或 None

        Returns:
            {"status": "success", "data": {"answer": "...", "context_docs": [...]}}
        """
        logger.info(f"[KnowledgeAgent] 处理: {prompt[:100]}...")

        try:
            kb_id = None
            if context:
                kb_id = context.get("kb_id") or context.get("knowledge_base_id")

            # ----- 模式 1: 文档入库 -----
            if context and context.get("file_path") and kb_id:
                return self._ingest_document(
                    file_path=context["file_path"],
                    knowledge_base_id=kb_id,
                )

            # ----- 模式 2: 知识库问答 -----
            if kb_id:
                result = self.engine.answer_question(
                    question=prompt,
                    knowledge_base_id=kb_id,
                    system_prompt=context.get("system_prompt") if context else None,
                )
                source_count = len(result.get("context_docs", []))
                logger.info(f"[KnowledgeAgent] 检索到 {source_count} 条相关文档")
                return self._success(
                    data={
                        "answer": result["answer"],
                        "context_docs": result["context_docs"],
                        "source_count": source_count,
                    }
                )

            # ----- 模式 3: 通用对话（无知识库）-----
            # 直接使用 LLM 能力
            answer = self.ask_llm(prompt)
            return self._success(
                data={
                    "answer": answer,
                    "context_docs": [],
                    "source_count": 0,
                }
            )

        except Exception as e:
            logger.exception(f"[KnowledgeAgent] 执行失败: {e}")
            # 降级：直接 LLM 回答
            try:
                answer = self.ask_llm(prompt)
                return self._success(
                    data={
                        "answer": answer,
                        "context_docs": [],
                        "source_count": 0,
                        "note": f"知识库检索失败({str(e)[:50]})，已降级为 LLM 直接回答",
                    },
                    fallback=True,
                )
            except Exception:
                return self._error(f"知识检索失败: {str(e)}")

    # ================================================================
    # 文档入库
    # ================================================================

    def _ingest_document(self, file_path: str, knowledge_base_id: int) -> dict:
        """处理文档入库"""
        logger.info(f"[KnowledgeAgent] 文档入库: {file_path} → kb_{knowledge_base_id}")
        chunk_count = self.engine.process_document(
            file_path=file_path,
            knowledge_base_id=knowledge_base_id,
        )
        return self._success(
            data={
                "file": file_path,
                "kb_id": knowledge_base_id,
                "chunks": chunk_count,
                "message": f"已处理 {chunk_count} 个文本块并存入 Milvus",
            }
        )

    # ================================================================
    # 扩展能力
    # ================================================================

    def search(self, query: str, kb_id: int, top_k: int = 5) -> list:
        """直接向量检索（不做问答生成）"""
        from core.tools.milvus_store import get_milvus_store
        store = get_milvus_store()
        query_vector = self.engine.embeddings.embed_query(query)
        return store.search(
            query_vector=query_vector,
            top_k=top_k,
            kb_id=kb_id,
            similarity_threshold=0.5,
        )

    def delete_by_kb(self, kb_id: int):
        """删除指定知识库的全部向量"""
        self.engine.delete_knowledge_base_data(kb_id)

    def stream_answer(self, question: str, kb_id: int, system_prompt: str = None):
        """流式问答 — 用于 SSE 接口"""
        return self.engine.answer_question_stream(
            question=question,
            knowledge_base_id=kb_id,
            system_prompt=system_prompt,
        )


def create_knowledge_agent(kb_id: Optional[int] = None) -> KnowledgeAgent:
    """工厂函数：创建知识库 Agent"""
    return KnowledgeAgent(knowledge_base_id=kb_id)
