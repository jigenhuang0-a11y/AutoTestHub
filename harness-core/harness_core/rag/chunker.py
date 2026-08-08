"""RAG 知识中枢 - 文档分片（chunking）。

支持按字符/句子滑动窗口分片，为中文文档优化（避免切半句）。
P2 先用规则分片；P3 可接语义分片。
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class Chunk:
    text: str
    index: int
    metadata: dict = None  # type: ignore


def split_text(
    text: str, *, chunk_size: int = 500, overlap: int = 80
) -> list[Chunk]:
    """滑动窗口分片，按句子边界对齐。"""
    # 按中英文句号/换行切句
    sentences = re.split(r"(?<=[。！？\.\!\?\n])", text)
    sentences = [s.strip() for s in sentences if s.strip()]
    chunks: list[Chunk] = []
    buf = ""
    idx = 0
    for sent in sentences:
        if len(buf) + len(sent) > chunk_size and buf:
            chunks.append(Chunk(text=buf, index=idx))
            idx += 1
            # 保留 overlap 尾部
            buf = buf[-overlap:] if overlap else ""
        buf += sent
    if buf:
        chunks.append(Chunk(text=buf, index=idx))
    return chunks
