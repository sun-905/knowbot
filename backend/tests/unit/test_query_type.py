"""查询类型分类器单元测试"""
import pytest
from app.services.query_type import classify_query_type, get_effective_top_k


class TestClassifyQueryType:
    """查询类型分类测试"""

    def test_comparison_vs(self):
        """含 vs 的比较查询 → complex"""
        assert classify_query_type("X1 vs X2 哪个好") == "complex"

    def test_comparison_duibi(self):
        """含 对比 的比较查询 → complex"""
        assert classify_query_type("对比一下A和B的区别") == "complex"

    def test_comparison_qubie(self):
        """含 区别 → complex"""
        assert classify_query_type("A和B有什么区别") == "complex"

    def test_comparison_which_better(self):
        """含 哪个更好 → complex"""
        assert classify_query_type("这两个哪个更好") == "complex"

    def test_comparison_youquedian(self):
        """含 优缺点 → complex"""
        assert classify_query_type("这个产品的优缺点是什么") == "complex"

    def test_complex_why(self):
        """含 为什么 → complex"""
        assert classify_query_type("为什么退款这么慢") == "complex"

    def test_complex_how_to_solve(self):
        """含 如何解决 → complex"""
        assert classify_query_type("登录失败如何解决") == "complex"

    def test_complex_liucheng(self):
        """含 流程是什么 → complex"""
        assert classify_query_type("退货流程是什么") == "complex"

    def test_complex_conditional(self):
        """含假设条件 → complex"""
        assert classify_query_type("如果退货被拒怎么办") == "complex"

    def test_long_query_complex(self):
        """长查询 >30字 → complex"""
        long_q = "我想详细了解一下这个智能门锁产品的所有功能细节和使用方法以及售后政策条款退换货流程"  # >30字
        assert classify_query_type(long_q) == "complex"

    def test_simple_short_fact(self):
        """短事实查询 → simple"""
        assert classify_query_type("X1多少钱") == "simple"

    def test_simple_single_entity(self):
        """单实体查询 → simple"""
        assert classify_query_type("退货期限是多久") == "simple"

    def test_simple_how_to(self):
        """简单操作 → simple（不含复杂词）"""
        assert classify_query_type("如何申请退货") == "simple"

    def test_empty_message(self):
        """空消息 → simple"""
        assert classify_query_type("") == "simple"

    def test_greeting(self):
        """问候 → simple"""
        assert classify_query_type("你好") == "simple"


class TestGetEffectiveTopK:
    """动态 K 选择测试"""

    def test_simple_uses_floor(self):
        """简单查询使用 K_floor"""
        import app.services.query_type as qt
        from unittest.mock import patch
        mock_settings = patch.object(qt, 'settings')
        with mock_settings as s:
            s.retrieval_top_k = 5
            s.retrieval_top_k_floor = 3
            s.retrieval_top_k_opt = 8
            k = get_effective_top_k("X1多少钱")
            assert k == 3  # simple → floor

    def test_complex_uses_opt(self):
        """复杂查询使用 K_opt"""
        import app.services.query_type as qt
        from unittest.mock import patch
        mock_settings = patch.object(qt, 'settings')
        with mock_settings as s:
            s.retrieval_top_k = 5
            s.retrieval_top_k_floor = 3
            s.retrieval_top_k_opt = 8
            k = get_effective_top_k("对比A和B的区别")
            assert k == 8  # complex → opt

    def test_fallback_when_uncalibrated(self):
        """未校准时回退到默认值"""
        import app.services.query_type as qt
        from unittest.mock import patch
        mock_settings = patch.object(qt, 'settings')
        with mock_settings as s:
            s.retrieval_top_k = 5
            s.retrieval_top_k_floor = 0  # 未校准
            s.retrieval_top_k_opt = 0    # 未校准
            k_simple = get_effective_top_k("你好")
            k_complex = get_effective_top_k("对比A和B")
            assert k_simple == 5  # fallback
            assert k_complex == 5  # fallback
