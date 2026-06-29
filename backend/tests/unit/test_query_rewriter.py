"""查询改写服务单元测试"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from app.services.query_rewriter import rewrite_query, rewrite_query_sync


class TestRewriteQuery:
    """rewrite_query 单元测试"""

    @pytest.mark.asyncio
    async def test_disabled_by_config(self):
        """配置关闭时返回原始消息"""
        with patch("app.services.query_rewriter.settings") as mock_settings:
            mock_settings.query_rewrite_enabled = False
            result = await rewrite_query("这玩意怎么退啊", intent="产品咨询")
            assert result == "这玩意怎么退啊"

    @pytest.mark.asyncio
    async def test_skip_casual_intent(self):
        """闲聊意图不改写"""
        with patch("app.services.query_rewriter.settings") as mock_settings:
            mock_settings.query_rewrite_enabled = True
            result = await rewrite_query("你好呀", intent="闲聊")
            assert result == "你好呀"

    @pytest.mark.asyncio
    async def test_skip_short_message(self):
        """过短消息不改写"""
        with patch("app.services.query_rewriter.settings") as mock_settings:
            mock_settings.query_rewrite_enabled = True
            result = await rewrite_query("嗯", intent="产品咨询")
            assert result == "嗯"

    @pytest.mark.asyncio
    async def test_skip_long_message(self):
        """过长消息不改写（可能是粘贴的文档）"""
        with patch("app.services.query_rewriter.settings") as mock_settings:
            mock_settings.query_rewrite_enabled = True
            long_msg = "这个问题" * 300  # >500 字
            result = await rewrite_query(long_msg, intent="产品咨询")
            assert result == long_msg

    @pytest.mark.asyncio
    async def test_rewrite_colloquial_to_professional(self):
        """口语化表达改写为专业术语"""
        with patch("app.services.query_rewriter.settings") as mock_settings:
            mock_settings.query_rewrite_enabled = True
            mock_settings.query_rewrite_timeout = 5.0
            mock_settings.query_rewrite_model = "deepseek-chat"

            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "退货流程说明"
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

            with patch("app.services.query_rewriter._get_deepseek", return_value=mock_client):
                result = await rewrite_query("这玩意怎么退啊", intent="售后问题")
                assert result == "退货流程说明"

    @pytest.mark.asyncio
    async def test_clean_numbered_output(self):
        """清理 LLM 的编号前缀输出"""
        with patch("app.services.query_rewriter.settings") as mock_settings:
            mock_settings.query_rewrite_enabled = True
            mock_settings.query_rewrite_timeout = 5.0
            mock_settings.query_rewrite_model = "deepseek-chat"

            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            # LLM 有时会输出带编号的结果
            mock_response.choices[0].message.content = "1. 产品退货流程"
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

            with patch("app.services.query_rewriter._get_deepseek", return_value=mock_client):
                result = await rewrite_query("怎么退", intent="售后问题")
                assert result == "产品退货流程"

    @pytest.mark.asyncio
    async def test_clean_prefix_labels(self):
        """清理 LLM 的 '改写：' 前缀输出"""
        with patch("app.services.query_rewriter.settings") as mock_settings:
            mock_settings.query_rewrite_enabled = True
            mock_settings.query_rewrite_timeout = 5.0
            mock_settings.query_rewrite_model = "deepseek-chat"

            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "改写：产品退货流程"
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

            with patch("app.services.query_rewriter._get_deepseek", return_value=mock_client):
                result = await rewrite_query("怎么退", intent="售后问题")
                assert result == "产品退货流程"

    @pytest.mark.asyncio
    async def test_clean_quotes(self):
        """清理 LLM 输出的引号包裹"""
        with patch("app.services.query_rewriter.settings") as mock_settings:
            mock_settings.query_rewrite_enabled = True
            mock_settings.query_rewrite_timeout = 5.0
            mock_settings.query_rewrite_model = "deepseek-chat"

            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = '"退货流程说明"'
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

            with patch("app.services.query_rewriter._get_deepseek", return_value=mock_client):
                result = await rewrite_query("怎么退", intent="售后问题")
                assert result == "退货流程说明"

    @pytest.mark.asyncio
    async def test_timeout_fallback(self):
        """超时时降级为原始查询"""
        with patch("app.services.query_rewriter.settings") as mock_settings:
            mock_settings.query_rewrite_enabled = True
            mock_settings.query_rewrite_timeout = 0.001  # 极短超时

            import asyncio
            mock_client = AsyncMock()
            # 模拟 LLM 调用特别慢
            async def slow_response(**kwargs):
                await asyncio.sleep(10)
            mock_client.chat.completions.create = slow_response

            with patch("app.services.query_rewriter._get_deepseek", return_value=mock_client):
                result = await rewrite_query("这玩意怎么退", intent="售后问题")
                assert result == "这玩意怎么退"  # 降级返回原始

    @pytest.mark.asyncio
    async def test_empty_rewrite_result_fallback(self):
        """改写结果为空时降级"""
        with patch("app.services.query_rewriter.settings") as mock_settings:
            mock_settings.query_rewrite_enabled = True
            mock_settings.query_rewrite_timeout = 5.0
            mock_settings.query_rewrite_model = "deepseek-chat"

            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = " "  # 空白结果
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

            with patch("app.services.query_rewriter._get_deepseek", return_value=mock_client):
                result = await rewrite_query("怎么退", intent="售后问题")
                assert result == "怎么退"  # 降级返回原始
