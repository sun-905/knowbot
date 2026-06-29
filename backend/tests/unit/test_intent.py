"""意图识别单元测试"""
import pytest
from unittest.mock import patch, AsyncMock
from app.services.intent import _l1_rule_match, _l2_vector_match, _l3_llm_classify, classify_intent


class TestL1RuleMatch:
    def test_complaint_keyword(self):
        result = _l1_rule_match("我要投诉，产品质量太差了")
        assert result is not None
        assert result["intent"] == "投诉"
        assert result["confidence"] >= 0.90
        assert result["source"] == "rule"

    def test_return_keyword(self):
        result = _l1_rule_match("我要退货，商品有质量问题")
        assert result is not None
        assert result["intent"] == "售后问题"

    def test_order_keyword(self):
        result = _l1_rule_match("我的订单到哪里了")
        assert result is not None
        assert result["intent"] == "订单查询"

    def test_product_keyword(self):
        result = _l1_rule_match("这个产品有什么功能")
        assert result is not None
        assert result["intent"] == "产品咨询"

    def test_chat_keyword(self):
        result = _l1_rule_match("你好呀")
        assert result is not None
        assert result["intent"] == "闲聊"

    def test_no_match(self):
        result = _l1_rule_match("xyz 无意义文本 abc")
        assert result is None


class TestL3LLMClassify:
    @pytest.mark.asyncio
    async def test_returns_intent_structure(self):
        mock_response = AsyncMock()
        mock_response.choices = [
            AsyncMock(message=AsyncMock(content='{"intent": "产品咨询", "confidence": 0.85}'))
        ]
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch("app.services.intent._get_deepseek", return_value=mock_client):
            result = await _l3_llm_classify("这个产品多少钱")
            assert result["intent"] == "产品咨询"
            assert result["source"] == "llm"
            assert "confidence" in result

    @pytest.mark.asyncio
    async def test_clarify_when_low_confidence(self):
        mock_response = AsyncMock()
        mock_response.choices = [
            AsyncMock(message=AsyncMock(content='{"intent": "其他", "confidence": 0.55}'))
        ]
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch("app.services.intent._get_deepseek", return_value=mock_client):
            result = await _l3_llm_classify("嗯...这个嘛...")
            # confidence=0.55 < 0.7 → clarify=True
            assert result.get("clarify") is True

    @pytest.mark.asyncio
    async def test_fallback_on_llm_error(self):
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=Exception("API Error"))

        with patch("app.services.intent._get_deepseek", return_value=mock_client):
            result = await _l3_llm_classify("随便什么文本")
            assert result["intent"] == "其他"
            assert result["source"] == "llm"
            assert result["clarify"] is False
