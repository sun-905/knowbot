"""上下文守护单元测试 — 分层摘要、类型排序、实体提取、否定检测、生成后验证"""
import pytest
from app.services.context_guard import (
    stratified_summarize,
    prioritize_by_type,
    classify_chunk_type,
    verify_answer,
    _estimate_tokens,
    _extract_entities,
    _has_negation,
)


# ==================== 分层摘要 ====================

class TestStratifiedSummarize:
    def test_core_kept_full(self):
        """core 层（>=0.85）保留完整文本"""
        candidates = [{"text": "这是一段核心规则文本，包含退货必须在7天内申请的重要信息", "rerank_score": 0.90, "doc_name": "售后政策.md"}]
        result = stratified_summarize(candidates, max_tokens=500)
        assert len(result) == 1
        assert result[0]["tier"] == "core"
        assert "7天内" in result[0]["text"]

    def test_reference_truncated(self):
        """reference 层（0.70-0.84）截断至前 200 字"""
        long_text = "流程" * 300  # 600 字
        candidates = [{"text": long_text, "rerank_score": 0.75, "doc_name": "流程.md"}]
        result = stratified_summarize(candidates, max_tokens=500)
        assert len(result) == 1
        assert result[0]["tier"] == "reference"
        assert len(result[0]["text"]) <= 200

    def test_edge_name_only(self):
        """edge 层（<0.70）仅保留文档名"""
        candidates = [{"text": "边缘信息" * 50, "rerank_score": 0.50, "doc_name": "杂项.txt"}]
        result = stratified_summarize(candidates, max_tokens=500)
        assert len(result) == 1
        assert result[0]["tier"] == "edge"
        assert "杂项" in result[0]["text"]

    def test_token_budget_enforced(self):
        """token 预算限制，总量不超过 max_tokens"""
        candidates = [
            {"text": "核心规则" * 100, "rerank_score": 0.90, "doc_name": "a.md"},
            {"text": "参考信息" * 100, "rerank_score": 0.75, "doc_name": "b.md"},
            {"text": "边缘补充" * 100, "rerank_score": 0.50, "doc_name": "c.md"},
        ]
        result = stratified_summarize(candidates, max_tokens=100)
        total_tokens = sum(_estimate_tokens(r["text"]) for r in result)
        assert total_tokens <= 100

    def test_empty_candidates(self):
        """空候选列表返回空"""
        assert stratified_summarize([], max_tokens=500) == []

    def test_uses_rerank_score_first(self):
        """优先使用 rerank_score，其次 rrf，最后 score"""
        candidates = [
            {"text": "用 rerank_score", "rerank_score": 0.92, "rrf": 0.50, "score": 0.40, "doc_name": "a.md"},
        ]
        result = stratified_summarize(candidates, max_tokens=500)
        assert result[0]["tier"] == "core"

    def test_falls_back_to_rrf(self):
        """无 rerank_score 时使用 rrf"""
        candidates = [
            {"text": "用 rrf 分数", "rrf": 0.80, "score": 0.40, "doc_name": "a.md"},
        ]
        result = stratified_summarize(candidates, max_tokens=500)
        assert result[0]["tier"] == "reference"

    def test_falls_back_to_score(self):
        """无 rerank_score 和 rrf 时使用 score"""
        candidates = [
            {"text": "用原始分数", "score": 0.60, "doc_name": "a.md"},
        ]
        result = stratified_summarize(candidates, max_tokens=500)
        assert result[0]["tier"] == "edge"


# ==================== 类型分类 ====================

class TestClassifyChunkType:
    def test_rule_keyword_must(self):
        assert classify_chunk_type("必须在7天内退货") == "规则"

    def test_rule_keyword_forbidden(self):
        assert classify_chunk_type("禁止无理由退货") == "规则"

    def test_procedure_keyword_steps(self):
        assert classify_chunk_type("申请退货的步骤：登录→我的订单") == "流程"

    def test_procedure_keyword_how(self):
        assert classify_chunk_type("如何查询物流信息") == "流程"

    def test_fact_default(self):
        assert classify_chunk_type("产品售价1299元，颜色有黑白两种") == "事实"


# ==================== 类型排序 ====================

class TestPrioritizeByType:
    def test_rules_first(self):
        """规则排在最前面"""
        candidates = [
            {"text": "如何申请退货", "doc_name": "a.md"},
            {"text": "必须在7天内退货", "doc_name": "b.md"},
            {"text": "产品售价1299元", "doc_name": "c.md"},
        ]
        result = prioritize_by_type(candidates)
        assert result[0]["chunk_type"] == "规则"

    def test_facts_before_procedures(self):
        """事实在流程之前"""
        candidates = [
            {"text": "如何登录账户", "doc_name": "a.md"},
            {"text": "产品重1.2kg", "doc_name": "b.md"},
        ]
        result = prioritize_by_type(candidates)
        assert result[0]["chunk_type"] == "事实"
        assert result[1]["chunk_type"] == "流程"


# ==================== 实体提取 ====================

class TestExtractEntities:
    def test_numbers_with_unit(self):
        ents = _extract_entities("退货期限为 7 天，保修 1 年")
        assert "7" in " ".join(ents["numbers"])
        assert "1" in " ".join(ents["numbers"])

    def test_dates(self):
        ents = _extract_entities("2026年6月28日起生效，截止2026-12-31")
        assert len(ents["dates"]) > 0

    def test_quoted_terms(self):
        ents = _extract_entities('请参考《售后政策》和「用户协议」')
        assert any("售后政策" in q for q in ents["quoted"])
        assert any("用户协议" in q for q in ents["quoted"])

    def test_empty_text(self):
        ents = _extract_entities("")
        assert ents == {"numbers": set(), "dates": set(), "quoted": set()}


# ==================== 否定检测 ====================

class TestHasNegation:
    def test_detects_bu(self):
        assert _has_negation("不能在7天后退货") is True

    def test_detects_jinzhi(self):
        assert _has_negation("禁止无理由退款") is True

    def test_detects_meiyou(self):
        assert _has_negation("没有相关信息") is True

    def test_no_negation(self):
        assert _has_negation("请在7天内申请退货") is False

    def test_empty(self):
        assert _has_negation("") is False


# ==================== 生成后验证 ====================

class TestVerifyAnswer:
    def test_token_overlap_pass(self):
        """token 重叠 >= 30% 通过"""
        answer = "退货期限为7天。"
        sources = [{"text": "退货需在收到商品后7天内申请"}]
        result = verify_answer(answer, sources)
        assert result["pass"] is True

    def test_entity_match_pass(self):
        """实体匹配（数字）通过"""
        answer = "售价为1299元。"
        sources = [{"text": "产品售价1299元，包含一年保修"}]
        result = verify_answer(answer, sources)
        assert result["pass"] is True

    def test_negation_mismatch_flag(self):
        """编造的信息与来源无交集，必须被标记"""
        answer = "本店支持，货到付款，包邮配送，覆盖全国，当日发货。"
        sources = [{"text": "退货期限为7天，超过7天需要联系客服"}]
        result = verify_answer(answer, sources)
        assert result["pass"] is False

    def test_all_sentences_checked(self):
        """全部句子检查，不只是前5句"""
        answer = "本店支持，货到付款，包邮配送，覆盖全国，当日发货。"
        sources = [{"text": "我们只销售X1和X2两个产品"}]
        result = verify_answer(answer, sources)
        assert result["pass"] is False
        assert len(result["unverified_claims"]) >= 1

    def test_short_claim_skipped(self):
        """少于10字的声明跳过"""
        answer = "好。的。可以。"
        sources = [{"text": "可以退货"}]
        result = verify_answer(answer, sources)
        assert result["pass"] is True

    def test_no_sources_fails(self):
        """无来源时所有声明都未验证"""
        answer = "产品售价1299元，保修一年。"
        sources = []
        result = verify_answer(answer, sources)
        assert result["pass"] is False
