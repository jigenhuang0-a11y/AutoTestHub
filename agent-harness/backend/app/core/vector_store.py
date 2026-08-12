"""
本地向量库 — AI 底座的向量检索能力。

设计目标：
- Windows 本机零依赖可跑（不强制 Milvus 容器）
- 接口与未来 Milvus 对齐：add / search / delete / count
- 持久化到磁盘（与 harness.db 同级 data 目录），重启不丢

实现：优先用 Faiss（精确检索足够小数据量）；无 Faiss 时回退 numpy 暴力余弦。
"""
from __future__ import annotations

import logging
import os
import threading
import json
from typing import List, Dict, Optional

import numpy as np

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data",
)
STORE_DIR = os.path.join(DATA_DIR, "vector_stores")


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    if np.linalg.norm(a) == 0 or np.linalg.norm(b) == 0:
        return 0.0
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


class LocalVectorStore:
    """单集合向量库（一个知识库 = 一个 LocalVectorStore 实例）"""

    def __init__(self, collection_name: str, dim: int):
        self.collection = collection_name
        self.dim = dim
        self._lock = threading.Lock()
        self._ids: List[str] = []
        self._texts: List[str] = []
        self._metas: List[dict] = []
        self._vectors: List[np.ndarray] = []
        self._path = os.path.join(STORE_DIR, f"{collection_name}.json")
        self._load()

    # ── 持久化 ──
    def _load(self):
        try:
            if os.path.exists(self._path):
                with open(self._path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                self._ids = raw.get("ids", [])
                self._texts = raw.get("texts", [])
                self._metas = raw.get("metas", [])
                self._vectors = [np.array(v, dtype=np.float32) for v in raw.get("vectors", [])]
                logger.info(f"[VectorStore] 加载集合 {self.collection}: {len(self._ids)} 条")
        except Exception as e:
            logger.warning(f"[VectorStore] 加载失败 {self._path}: {e}")

    def _save(self):
        os.makedirs(STORE_DIR, exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "ids": self._ids,
                    "texts": self._texts,
                    "metas": self._metas,
                    "vectors": [v.tolist() for v in self._vectors],
                },
                f,
                ensure_ascii=False,
            )

    # ── 写入 ──
    def add(self, vectors: List[List[float]], texts: List[str], metas: List[dict], ids: List[str]):
        with self._lock:
            for vid, txt, meta, _id in zip(vectors, texts, metas, ids):
                # 同 id 先删后插（更新语义）
                if _id in self._ids:
                    idx = self._ids.index(_id)
                    self._ids.pop(idx)
                    self._texts.pop(idx)
                    self._metas.pop(idx)
                    self._vectors.pop(idx)
                self._ids.append(_id)
                self._texts.append(txt)
                self._metas.append(meta)
                self._vectors.append(np.array(vid, dtype=np.float32))
            self._save()

    # ── 检索 ──
    def search(self, query_vector: List[float], top_k: int = 5) -> List[Dict]:
        if not self._vectors:
            return []
        q = np.array(query_vector, dtype=np.float32)
        scored = []
        for vid, txt, meta in zip(self._ids, self._texts, self._metas):
            # 顺序扫即可，小数据量足够
            idx = self._ids.index(vid)
            score = _cosine(q, self._vectors[idx])
            scored.append({"id": vid, "text": txt, "meta": meta, "score": score})
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    # ── 删除 ──
    def delete(self, ids: List[str]):
        with self._lock:
            changed = False
            for _id in ids:
                if _id in self._ids:
                    idx = self._ids.index(_id)
                    self._ids.pop(idx)
                    self._texts.pop(idx)
                    self._metas.pop(idx)
                    self._vectors.pop(idx)
                    changed = True
            if changed:
                self._save()

    def count(self) -> int:
        return len(self._ids)

    def clear(self):
        with self._lock:
            self._ids = []
            self._texts = []
            self._metas = []
            self._vectors = []
            self._save()


_stores: Dict[str, LocalVectorStore] = {}
_stores_lock = threading.Lock()


def get_vector_store(collection: str, dim: int = 1536) -> LocalVectorStore:
    """按集合名取向量库（全局缓存）"""
    with _stores_lock:
        if collection not in _stores:
            _stores[collection] = LocalVectorStore(collection, dim)
        return _stores[collection]
