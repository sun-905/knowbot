import asyncio
import re
from collections import defaultdict

import numpy as np
from loguru import logger
from rank_bm25 import BM25Okapi
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..core.embedding import encode_query
from ..core.qdrant_client import COLLECTION_NAME, get_qdrant

# --- BM25 索引（模块级）---
_bm25: BM25Okapi | None = None
_bm25_keys: list[str] = []  # "doc_id:chunk_index" 格式的键
_bm25_texts: list[str] = []
_bm25_tokenized: list[list[str]] = []


def _tokenize(text: str) -> list[str]:
    """简单的中英文分词：按非单词字符切分，过滤空白"""
    return [t for t in re.split(r"[^\w]+", text.lower()) if t]


def rebuild_bm25() -> None:
    """重置 BM25 索引"""
    global _bm25, _bm25_keys, _bm25_texts, _bm25_tokenized
    _bm25_keys = []
    _bm25_texts = []
    _bm25_tokenized = []
    _bm25 = None


def add_to_bm25(key: str, text: str) -> None:
    """增量添加文档到 BM25 索引"""
    global _bm25_keys, _bm25_texts, _bm25_tokenized, _bm25
    _bm25_keys.append(key)
    _bm25_texts.append(text)
    tokens = _tokenize(text)
    _bm25_tokenized.append(tokens)
    if _bm25 is not None:
        # 增量：用全部数据重建
        _bm25 = BM25Okapi(_bm25_tokenized)
    elif len(_bm25_tokenized) >= 1:
        _bm25 = BM25Okapi(_bm25_tokenized)


def remove_from_bm25(key: str) -> None:
    """从 BM25 索引中删除文档"""
    global _bm25_keys, _bm25_texts, _bm25_tokenized, _bm25
    try:
        idx = _bm25_keys.index(key)
        _bm25_keys.pop(idx)
        _bm25_texts.pop(idx)
        _bm25_tokenized.pop(idx)
        if _bm25_tokenized:
            _bm25 = BM25Okapi(_bm25_tokenized)
        else:
            _bm25 = None
    except ValueError:
        pass


# --- 检索 ---

async def vector_search(query: str, kb_id: int | None = None, k: int | None = None) -> list[dict]:
    """Qdrant 向量检索"""
    if k is None:
        k = settings.retrieval_coarse_k
    qv = await encode_query(query)
    qdrant = await get_qdrant()

    query_filter = None
    if kb_id is not None:
        from qdrant_client.http import models as qmodels
        query_filter = qmodels.Filter(
            must=[qmodels.FieldCondition(key="kb_id", match=qmodels.MatchValue(value=kb_id))]
        )

    results = qdrant.search(
        collection_name=COLLECTION_NAME,
        query_vector=qv.tolist(),
        limit=k,
        query_filter=query_filter,
        with_payload=True,
    )
    return [
        {
            "id": r.id,
            "score": r.score,
            "kb_id": r.payload.get("kb_id"),
            "doc_id": r.payload.get("doc_id"),
            "doc_name": r.payload.get("doc_name", ""),
            "chunk_index": r.payload.get("chunk_index", 0),
            "text": r.payload.get("text", ""),
            "source": "vector",
        }
        for r in results
    ]


def keyword_search(query: str, k: int = 20) -> list[dict]:
    """BM25 关键词检索"""
    if _bm25 is None or not _bm25_tokenized:
        return []

    tokens = _tokenize(query)
    scores = _bm25.get_scores(tokens)

    # 归一化到 [0, 1]
    max_score = max(scores) if max(scores) > 0 else 1
    normalized = scores / max_score

    # 取 top-k
    indices = np.argsort(normalized)[::-1][:k]
    results = []
    for idx in indices:
        if normalized[idx] <= 0:
            continue
        doc_id = 0
        chunk_idx = 0
        key_parts = _bm25_keys[idx].split(":", 1)
        if len(key_parts) == 2:
            doc_id = int(key_parts[0])
            chunk_idx = int(key_parts[1])
        results.append({
            "id": f"bm25_{_bm25_keys[idx]}",
            "score": float(normalized[idx]),
            "doc_id": doc_id,
            "chunk_index": chunk_idx,
            "text": _bm25_texts[idx],
            "source": "bm25",
        })
    return results


async def hybrid_search(query: str, kb_id: int | None = None) -> list[dict]:
    """混合检索：向量 + BM25，RRF 融合"""
    v_results, k_results = await asyncio.gather(
        vector_search(query, kb_id),
        asyncio.to_thread(keyword_search, query),
    )

    # RRF（倒数排名融合）
    rrf_scores: dict[str, dict] = {}
    for rank, item in enumerate(v_results, 1):
        key = f"v_{item['id']}"
        rrf_scores[key] = {**item, "rrf": 1.0 / (60 + rank)}

    for rank, item in enumerate(k_results, 1):
        key = f"k_{item['id']}"
        existing = rrf_scores.get(key, {**item, "rrf": 0})
        existing["rrf"] = existing.get("rrf", 0) + 1.0 / (60 + rank)
        # 合并来源标记
        if existing.get("source") != item["source"]:
            existing["source"] = "hybrid"
        if "kb_id" not in existing and "kb_id" in item:
            existing["kb_id"] = item["kb_id"]
        rrf_scores[key] = existing

    merged = sorted(rrf_scores.values(), key=lambda x: x["rrf"], reverse=True)
    return merged[:20]  # 返回 top-20 候选给重排序器


# --- 重排序器 ---
_reranker = None


async def _get_reranker():
    """懒加载重排序模型，GPU 优先，不可用时降级 CPU"""
    global _reranker
    if _reranker is None:
        import torch
        from FlagEmbedding import FlagReranker

        gpu_available = torch.cuda.is_available()
        if gpu_available:
            try:
                _reranker = FlagReranker("BAAI/bge-reranker-v2-m3", use_fp16=True)
                logger.info("重排序模型已加载到 GPU")
            except Exception as e:
                logger.warning(f"GPU 加载重排序模型失败，降级 CPU: {e}")
                _reranker = FlagReranker("BAAI/bge-reranker-v2-m3", use_fp16=False)
        else:
            _reranker = FlagReranker("BAAI/bge-reranker-v2-m3", use_fp16=False)
            logger.info("重排序模型已加载到 CPU（CUDA 不可用）")
    return _reranker


async def preload_reranker():
    """启动时预热：提前加载重排序模型，避免首次对话等待 30s"""
    from loguru import logger
    logger.info("正在预热重排序模型 (bge-reranker-v2-m3)...")
    await _get_reranker()
    logger.info("重排序模型预热完成")


async def rerank(query: str, candidates: list[dict], top_n: int = 10) -> list[dict]:
    """Cross-Encoder 重排序，带超时兜底（首次加载模型需 5-10s）"""
    if not candidates:
        return []

    reranker = await _get_reranker()
    pairs = [[query, c["text"][:1000]] for c in candidates]  # GPU 默认，可取更长文本

    try:
        scores = await asyncio.wait_for(
            asyncio.to_thread(reranker.compute_score, pairs),
            timeout=8.0,  # 超过 8s 直接降级，用户体验优先
        )
    except asyncio.TimeoutError:
        logger.warning("重排序器超时 — 降级使用融合结果")
        return candidates[:top_n]

    if isinstance(scores, float):
        scores = [scores]

    for i, score in enumerate(scores):
        candidates[i]["rerank_score"] = float(score)

    # 归一化到 [0, 1]，供分层摘要的阈值判定使用
    raw_scores = [c["rerank_score"] for c in candidates]
    min_s, max_s = min(raw_scores), max(raw_scores)
    if max_s - min_s > 0.001:
        for c in candidates:
            c["rerank_score"] = round((c["rerank_score"] - min_s) / (max_s - min_s), 4)

    candidates.sort(key=lambda x: x.get("rerank_score", 0), reverse=True)
    return candidates[:top_n]
