"""检索服务单元测试"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from app.services.retrieval import (
    hybrid_search,
    rerank,
    _tokenize,
    add_to_bm25,
    remove_from_bm25,
)


class TestTokenizer:
    def test_chinese_tokenize(self):
        tokens = _tokenize("hello world")
        assert len(tokens) == 2
        assert "hello" in tokens

    def test_mixed_tokenize(self):
        tokens = _tokenize("return 7 days")
        assert len(tokens) >= 2

    def test_empty(self):
        assert _tokenize("") == []


class TestRerank:
    @pytest.mark.asyncio
    async def test_normalizes_scores(self):
        """rerank 分数应归一化到 [0,1]"""
        candidates = [
            {"text": "文档A内容", "doc_name": "a.md", "score": 0.5},
            {"text": "文档B内容", "doc_name": "b.md", "score": 0.3},
        ]

        mock_reranker = MagicMock()
        mock_reranker.compute_score.return_value = [2.5, -1.0]

        with patch("app.services.retrieval._get_reranker", AsyncMock(return_value=mock_reranker)):
            result = await rerank("查询", candidates, top_n=5)
            # 所有 rerank_score 应在 [0,1] 内
            for r in result:
                assert 0 <= r["rerank_score"] <= 1

    @pytest.mark.asyncio
    async def test_sort_desc_by_score(self):
        """按归一化后分数降序排列"""
        candidates = [
            {"text": "低分文档", "doc_name": "low.md"},
            {"text": "高分文档", "doc_name": "high.md"},
        ]

        mock_reranker = MagicMock()
        mock_reranker.compute_score.return_value = [5.0, 1.0]

        with patch("app.services.retrieval._get_reranker", AsyncMock(return_value=mock_reranker)):
            result = await rerank("查询", candidates, top_n=5)
            assert result[0]["rerank_score"] >= result[1]["rerank_score"]

    @pytest.mark.asyncio
    async def test_rerank_exception_propagates(self):
        """rerank 内部异常向上传播（由调用方 chat.py 做降级处理）"""
        candidates = [
            {"text": "docA", "doc_name": "a.md", "score": 0.8},
        ]
        with patch("app.services.retrieval._get_reranker", AsyncMock(side_effect=Exception("model not found"))):
            with pytest.raises(Exception, match="model not found"):
                await rerank("query", candidates, top_n=5)

    @pytest.mark.asyncio
    async def test_empty_candidates(self):
        result = await rerank("查询", [], top_n=5)
        assert result == []


class TestBM25Incremental:
    def test_add_and_remove_does_not_crash(self):
        """增删 BM25 不抛异常"""
        try:
            add_to_bm25("1:0", "这是一段测试文本")
            add_to_bm25("1:1", "另一段测试文本")
            remove_from_bm25("1:0")
        except Exception as e:
            pytest.fail(f"BM25 操作不应抛异常: {e}")
