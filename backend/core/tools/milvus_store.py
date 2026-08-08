"""
Milvus 企业级向量数据库存储层

支持：
- 本地 Milvus Lite（无需 Docker，默认）
- 远程 Milvus 服务器
- 亿级向量存储与检索
- 多种索引策略 (HNSW / IVF_FLAT / IVF_PQ)
- 按知识库 ID 过滤检索

使用方式:
    from core.tools.milvus_store import MilvusStore
    
    store = MilvusStore(
        collection_name='ai_test_knowledge',
        embedding_dim=1024,
        uri='./milvus_data/milvus.db',  # 本地 Milvus Lite
    )
    
    # 插入向量
    store.upsert(ids=['1','2','3'], vectors=[[...], [...], [...]],
                 contents=['...','...','...'], kb_ids=[1,1,1])
    
    # 检索
    results = store.search(query_vector=[...], top_k=5, kb_id=1)
"""
import logging
import time
import os
from typing import Optional

logger = logging.getLogger(__name__)

# 延迟导入 pymilvus（避免未安装时崩溃）
try:
    from pymilvus import MilvusClient  # v2.4+ 推荐的新版 API
    MILVUS_AVAILABLE = True
except ImportError:
    MilvusClient = None
    MILVUS_AVAILABLE = False


class MilvusConnectionError(Exception):
    """Milvus 连接失败"""
    pass


class MilvusStore:
    """
    Milvus 向量数据库操作封装 (使用 MilvusClient v2.4+ API)

    设计原则:
    - 自动连接管理
    - Collection 自动创建/复用
    - 按 kb_id 过滤隔离知识库
    - 支持 HNSW(高精度) / IVF_PQ(高压缩) 索引
    """

    def __init__(
        self,
        collection_name: str = "ai_test_knowledge",
        embedding_dim: int = 1024,
        uri: str = None,           # 如 "http://localhost:19530"
        host: str = "localhost",
        port: int = 19530,
        index_type: str = "HNSW",       # HNSW / IVF_FLAT / IVF_PQ
        metric_type: str = "COSINE",     # COSINE / L2 / IP
    ):
        self.collection_name = collection_name
        self.embedding_dim = embedding_dim
        self.index_type = index_type.upper()
        self.metric_type = metric_type.upper()

        if not MILVUS_AVAILABLE:
            raise ImportError("pymilvus 未安装: pip install pymilvus>=2.4.0")

        # 构建连接 URI：优先使用传入的 uri（支持 Milvus Lite 本地文件模式）
        # 例如: uri="./milvus.db" 使用本地嵌入式数据库，无需 Docker
        self._uri = uri or f"http://{host}:{port}"
        self._client: Optional[MilvusClient] = None

    @property
    def client(self) -> MilvusClient:
        """懒初始化客户端（单例）"""
        if self._client is None:
            try:
                self._client = MilvusClient(uri=self._uri)
                logger.info(f"[Milvus] 已连接 {self._uri}")
            except Exception as e:
                raise MilvusConnectionError(f"无法连接 Milvus ({self._uri}): {e}")
        return self._client

    def health_check(self) -> dict:
        """健康检查 + 延迟测试"""
        start = time.time()
        try:
            c = self.client
            latency_ms = (time.time() - start) * 1000
            exists = c.has_collection(self.collection_name)
            return {
                "status": "ok",
                "uri": self._uri,
                "collection_exists": exists,
                "latency_ms": round(latency_ms, 2),
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "latency_ms": round((time.time() - start) * 1000, 2),
            }

    # ================================================================
    # Collection 管理
    # ================================================================

    def _ensure_collection(self):
        """确保 Collection 存在且有索引"""
        c = self.client

        if not c.has_collection(self.collection_name):
            schema = self._build_schema()
            c.create_collection(collection_name=self.collection_name, schema=schema)
            
            # 创建索引（Milvus Lite 只支持 FLAT/IVF_FLAT/AUTOINDEX）
            index_params = c.prepare_index_params()
            # Milvus Lite 本地模式不支持 HNSW，使用 AUTOINDEX 兼容
            idx_type = "AUTOINDEX" if "milvus.db" in self._uri else self.index_type
            idx_params = {} if idx_type == "AUTOINDEX" else {
                "M": 16, "efConstruction": 256
            }
            index_params.add_index(
                field_name="embedding",
                index_type=idx_type,
                metric_type=self.metric_type,
                params=idx_params,
            )
            c.create_index(
                collection_name=self.collection_name,
                index_params=index_params,
            )
            # 新创建的 collection 需要加载到内存才能搜索
            c.load_collection(self.collection_name)
            logger.info(f"[Milvus] Collection '{self.collection_name}' 创建成功 "
                       f"(dim={self.embedding_dim}, idx={idx_type})")
        else:
            # Collection 已存在：检查索引是否存在，如不存在则创建（兼容 Milvus Lite）
            try:
                c.load_collection(self.collection_name)
            except Exception:
                pass
            index_list = c.list_indexes(self.collection_name)
            if not index_list:
                logger.info(f"[Milvus] Collection 已存在但无索引，正在创建索引...")
                index_params = c.prepare_index_params()
                idx_type = "AUTOINDEX" if "milvus.db" in self._uri else self.index_type
                idx_params = {} if idx_type == "AUTOINDEX" else {
                    "M": 16, "efConstruction": 256
                }
                index_params.add_index(
                    field_name="embedding",
                    index_type=idx_type,
                    metric_type=self.metric_type,
                    params=idx_params,
                )
                c.create_index(
                    collection_name=self.collection_name,
                    index_params=index_params,
                )
                c.load_collection(self.collection_name)
                logger.info(f"[Milvus] 索引创建完成")

        return self.collection_name

    def _build_schema(self):
        """构建 Collection Schema"""
        from pymilvus import FieldSchema, CollectionSchema, DataType

        fields = [
            FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=128),
            FieldSchema(name="kb_id", dtype=DataType.VARCHAR, max_length=64),
            FieldSchema(name="doc_id", dtype=DataType.VARCHAR, max_length=128),
            FieldSchema(name="chunk_index", dtype=DataType.INT32),
            FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=8192),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.embedding_dim),
        ]
        return CollectionSchema(fields=fields, description=f"AI Test Platform Knowledge Base")

    # ================================================================
    # 数据操作 (CRUD)
    # ================================================================

    def upsert(
        self,
        ids: list[str],
        vectors: list[list[float]],
        contents: list[str],
        kb_ids: list[int],
        doc_ids: list[Optional[str]] = None,
        chunk_indices: list[int] = None,
    ) -> dict:
        """批量插入/更新向量"""
        start = time.time()
        col_name = self._ensure_collection()

        n = len(ids)
        doc_ids = doc_ids or [None] * n
        chunk_indices = chunk_indices or list(range(n))

        data = [
            {
                "id": ids[i],
                "kb_id": str(kb_ids[i]),
                "doc_id": str(doc_ids[i]) if doc_ids[i] else "",
                "chunk_index": chunk_indices[i],
                "content": contents[i],
                "embedding": vectors[i],
            }
            for i in range(n)
        ]

        self.client.upsert(collection_name=col_name, data=data)

        duration = time.time() - start
        logger.info(f"[Milvus] upsert {n} 条, 耗时 {duration:.3f}s")
        return {"inserted_count": n, "duration_ms": round(duration * 1000, 2)}

    def search(
        self,
        query_vector: list[float],
        top_k: int = 5,
        kb_id: Optional[int] = None,
        similarity_threshold: float = 0.0,
    ) -> list[dict]:
        """
        向量相似度搜索
        
        Returns:
            [{"id": ..., "score": 0.95, "content": ..., "metadata": {...}}, ...]
        """
        start = time.time()
        col_name = self._ensure_collection()

        filter_expr = f'kb_id == "{kb_id}"' if kb_id is not None else None

        # 搜索参数：AUTOINDEX（Milvus Lite）不需要额外参数，HNSW 需要 ef
        actual_idx_type = "AUTOINDEX" if "milvus.db" in self._uri else self.index_type
        search_extra = {"ef": 128} if actual_idx_type == "HNSW" else {}

        results = self.client.search(
            collection_name=col_name,
            data=[query_vector],
            anns_field="embedding",
            limit=top_k,
            search_params={
                "metric_type": self.metric_type,
                "params": search_extra,
            },
            output_fields=["id", "kb_id", "doc_id", "chunk_index", "content"],
        )

        hits_list = []
        for res in results:
            for hit in res:
                # 兼容 pymilvus 2.4 的 Hit 对象（非 dict，无 .get 方法）
                if isinstance(hit, dict):
                    entity = hit.get('entity', {})
                    distance = hit.get('distance', 0)
                else:
                    entity = hit.entity if hasattr(hit, 'entity') else {}
                    distance = hit.distance if hasattr(hit, 'distance') else 0
                
                # 如果 entity 不是 dict，转换为 dict
                if not isinstance(entity, dict):
                    entity = {k: getattr(entity, k, None) for k in ['id', 'kb_id', 'doc_id', 'chunk_index', 'content']}
                
                # Python 层面过滤 kb_id（Milvus Lite 的 filter 参数不兼容）
                if kb_id is not None and entity.get('kb_id') != str(kb_id):
                    continue
                
                score = float(distance)
                
                # Milvus COSINE 返回的 distance 本身就是 cosine_similarity（越大越相似）
                # 无需转换，直接作为相似度使用
                similarity = score
                
                if similarity < similarity_threshold:
                    continue

                hits_list.append({
                    "id": entity.get('id', ''),
                    "score": similarity,
                    "content": entity.get('content', ''),
                    "metadata": {
                        "kb_id": entity.get('kb_id', ''),
                        "doc_id": entity.get('doc_id', ''),
                        "chunk_index": entity.get('chunk_index'),
                        "distance": score,
                    },
                })

        duration = time.time() - start
        logger.debug(f"[Milvus] search top_k={top_k} kb={kb_id}, "
                     f"返回{len(hits_list)}条, 耗时{duration:.3f}s")
        return hits_list

    def delete_by_kb_id(self, kb_id: int) -> int:
        """删除指定知识库的所有向量"""
        col_name = self._ensure_collection()
        self.client.delete(
            collection_name=col_name,
            filter=f'kb_id == "{kb_id}"',
        )
        logger.info(f"[Milvus] 删除知识库 #{kb_id} 的所有向量数据")
        return 0

    def delete_by_doc_id(self, doc_id: int) -> int:
        """删除指定文档的所有向量"""
        col_name = self._ensure_collection()
        self.client.delete(
            collection_name=col_name,
            filter=f'doc_id == "{doc_id}"',
        )
        logger.info(f"[Milvus] 删除文档 #{doc_id} 的所有向量数据")
        return 0

    def delete_by_ids(self, vector_ids: list[str]) -> int:
        """删除指定 ID 列表的向量"""
        if not vector_ids:
            return 0
        col_name = self._ensure_collection()
        # MilvusClient.delete 使用 filter 表达式，ID 列表用 "in" 语法
        ids_str = ", ".join([f'"{vid}"' for vid in vector_ids])
        self.client.delete(
            collection_name=col_name,
            filter=f'id in [{ids_str}]',
        )
        logger.info(f"[Milvus] 批量删除 {len(vector_ids)} 条向量")
        return len(vector_ids)

    def get_stats(self) -> dict:
        """获取 Collection 统计信息"""
        c = self.client

        if not c.has_collection(self.collection_name):
            return {"status": "not_created"}

        stats = c.get_collection_stats(self.collection_name)
        
        indexes = []
        try:
            desc = c.describe_index(self.collection_name)
            indexes.append(desc)
        except Exception:
            pass

        return {
            "name": self.collection_name,
            "row_count": stats.get("row_count", 0),
            "indexes": indexes,
            "dim": self.embedding_dim,
            "index_type": self.index_type,
            "metric": self.metric_type,
        }

    def get_collection_stats(self, kb_id: int = None) -> dict:
        """获取知识库级别的向量统计信息

        Args:
            kb_id: 知识库 ID，None 则返回全局统计

        Returns:
            {"total_vectors": N, "collection_name": "...", "kb_id": kb_id}
        """
        base_stats = self.get_stats()
        
        if kb_id is not None:
            # 按 kb_id 过滤统计（查询 count）
            try:
                c = self.client
                if c.has_collection(self.collection_name):
                    results = c.query(
                        collection_name=self.collection_name,
                        filter=f'kb_id == "{kb_id}"',
                        output_fields=["id"],
                        limit=10000,
                    )
                    base_stats["total_vectors"] = len(results)
                else:
                    base_stats["total_vectors"] = 0
            except Exception as e:
                logger.warning(f"[Milvus] 按 kb_id 统计失败: {e}")
                base_stats["total_vectors"] = 0
        else:
            base_stats["total_vectors"] = base_stats.get("row_count", 0)

        base_stats["kb_id"] = kb_id
        return base_stats


# ================================================================
# 便捷工厂函数
# ================================================================

def get_milvus_store(collection_name: str = "ai_test_knowledge") -> MilvusStore:
    """
    从 Django settings 获取配置并返回 MilvusStore 实例
    
    默认使用 Milvus Lite（本地文件模式），无需 Docker 部署。
    如需远程 Milvus 服务器，在 settings 中配置 MILVUS_URI。
    
    注意：Milvus 是项目默认/唯一的向量数据库，不会自动降级到其他数据库。
    """
    from django.conf import settings
    
    if not MILVUS_AVAILABLE:
        raise ImportError("pymilvus 未安装，请执行: pip install pymilvus milvus-lite")
    
    # 优先使用 MILVUS_URI（支持本地文件或远程地址）
    milvus_uri = getattr(settings, 'MILVUS_URI', None)
    if not milvus_uri:
        # 默认使用 Milvus Lite 本地模式，数据文件存放在项目根目录
        milvus_uri = os.path.join(settings.BASE_DIR, 'milvus_data', 'milvus.db')
    
    # 对本地文件模式的 URI，提前创建父目录（Milvus Lite 不会自动创建）
    if milvus_uri and not milvus_uri.startswith(('http://', 'https://')):
        os.makedirs(os.path.dirname(milvus_uri) or '.', exist_ok=True)
    
    return MilvusStore(
        collection_name=getattr(settings, 'MILVUS_COLLECTION_NAME', collection_name),
        embedding_dim=1024,          # DashScope text-embedding-v3 输出维度
        uri=milvus_uri,
        index_type=os.getenv('MILVUS_INDEX_TYPE', 'HNSW'),
    )
