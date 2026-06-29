"""冒烟测试 — 验证 embedding + reranker 能否正常工作"""
import pytest
import asyncio
from app.core.embedding import encode
from app.services.retrieval import rerank


@pytest.mark.asyncio
async def test_embedding_works():
    """BGE 嵌入模型能正常编码"""
    emb = await encode(['测试文本'])
    assert emb.shape[0] == 1
    assert emb.shape[1] == 1024


@pytest.mark.asyncio
async def test_reranker_works():
    """重排序器能正常打分"""
    candidates = [
        {'text': 'X1售价1299元', 'doc_name': 'a.txt', 'score': 0.5},
        {'text': '退货期限7天内', 'doc_name': 'b.md', 'score': 0.3},
    ]
    result = await rerank('X1多少钱', candidates, top_n=5)
    assert len(result) > 0
    assert 'rerank_score' in result[0]
    assert 0 <= result[0]['rerank_score'] <= 1
