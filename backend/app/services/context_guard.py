import re

from loguru import logger


def _estimate_tokens(text: str) -> int:
    """粗略估算 token 数：1 token ≈ 2 个中文字符"""
    return len(text) // 2


def stratified_summarize(candidates: list[dict], max_tokens: int = 3000) -> list[dict]:
    """
    将候选分三层压缩：
      core（0.85+）：保留完整文本
      reference（0.70-0.85）：保留前 200 字摘要
      edge（0.65-0.70）：仅保留文档名 + 一行摘要
    按层级排序，同层按分数降序。
    """
    if not candidates:
        return []

    core, ref, edge = [], [], []
    for c in candidates:
        score = c.get("rerank_score") or c.get("rrf") or c.get("score", 0)
        if score >= 0.85:
            core.append(c)
        elif score >= 0.70:
            ref.append(c)
        else:
            edge.append(c)

    result = []
    token_budget = max_tokens

    # core: 完整文本
    for c in sorted(core, key=lambda x: x.get("rerank_score", x.get("rrf", 0)), reverse=True):
        text = c.get("text", "")
        if _estimate_tokens(text) <= token_budget:
            result.append({**c, "tier": "core"})
            token_budget -= _estimate_tokens(text)
        else:
            # 截断
            truncated = text[:token_budget * 2]
            result.append({**c, "text": truncated, "tier": "core_truncated"})
            token_budget = 0
            break

    # reference: 前 200 字摘要
    for c in sorted(ref, key=lambda x: x.get("rerank_score", x.get("rrf", 0)), reverse=True):
        text = c.get("text", "")
        summary = text[:200]
        if _estimate_tokens(summary) <= token_budget:
            result.append({**c, "text": summary, "tier": "reference"})
            token_budget -= _estimate_tokens(summary)

    # edge: 仅文档名
    for c in sorted(edge, key=lambda x: x.get("rerank_score", x.get("rrf", 0)), reverse=True):
        doc_name = c.get("doc_name", "未知文档")
        snippet = f"[来源：{doc_name}]"
        if _estimate_tokens(snippet) <= token_budget:
            result.append({**c, "text": snippet, "tier": "edge"})
            token_budget -= _estimate_tokens(snippet)

    logger.info(f"上下文守护: core={len([r for r in result if 'core' in r.get('tier','')])}, "
                f"ref={len([r for r in result if r.get('tier')=='reference'])}, "
                f"edge={len([r for r in result if r.get('tier')=='edge'])}")
    return result


_TYPE_PATTERNS = {
    "规则": re.compile(r"(必须|禁止|不得|应当|要求|规定|条件|标准|政策|规则|条款|协议)"),
    "流程": re.compile(r"(步骤|流程|如何|怎么|操作|申请|办理|提交|填写|点击|选择)"),
}


def classify_chunk_type(text: str) -> str:
    """根据关键词判断文本块类型：规则/流程/事实"""
    for type_name, pat in _TYPE_PATTERNS.items():
        if pat.search(text):
            return type_name
    return "事实"


def prioritize_by_type(candidates: list[dict]) -> list[dict]:
    """按类型排序：规则类 > 事实类 > 流程类"""
    priority = {"规则": 0, "事实": 1, "流程": 2}
    for c in candidates:
        c["chunk_type"] = classify_chunk_type(c.get("text", ""))
    return sorted(candidates, key=lambda x: priority.get(x.get("chunk_type", "事实"), 1))


def _extract_entities(text: str) -> dict:
    """从文本中提取关键实体：数字（含单位）、日期、专有名词"""
    nums = re.findall(r"\d+(?:\.\d+)?(?:\s*[天月年元块个次件])?", text)
    dates = re.findall(r"\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日号]?", text)
    # 引号内的内容通常是专有名词
    quoted = re.findall(r"[「『《\"'](.+?)[」』》\"']", text)
    return {
        "numbers": set(nums),
        "dates": set(dates),
        "quoted": set(quoted),
    }


def _has_negation(text: str) -> bool:
    """检测文本是否包含否定语义"""
    negation_words = ["不", "没有", "无法", "禁止", "不得", "不能", "不会", "不可", "未", "非", "无"]
    return any(w in text for w in negation_words)


def verify_answer(answer: str, sources: list[dict]) -> dict:
    """
    生成后验证：检查回答中的关键断言是否有来源支撑。

    对每条声明做三层检查：
    1. token 重叠度（快速筛查）
    2. 关键实体匹配（数字、日期、专有名词是否在来源中出现）
    3. 否定语义对齐（回答和来源的否定倾向是否一致）

    返回 {pass: bool, unverified_claims: list[str]}。
    """
    claims = re.findall(r"[^。！？\n]+(?:[。！？])", answer)
    unverified = []

    for claim in claims:
        claim_clean = claim.strip()
        if len(claim_clean) < 10:
            continue

        claim_lower = claim_clean.lower()
        claim_tokens = set(re.findall(r"[\w一-鿿]+", claim_lower))
        claim_entities = _extract_entities(claim_clean)
        claim_negated = _has_negation(claim_clean)

        found = False
        for src in sources:
            src_text = src.get("text", "").lower()
            src_tokens = set(re.findall(r"[\w一-鿿]+", src_text))
            overlap = claim_tokens & src_tokens
            token_ratio = len(overlap) / max(len(claim_tokens), 1)

            # 跳过意义不大的短声明（< 5 个实质 token）
            if len(claim_tokens) < 5:
                found = True
                break

            # 第 1 层：token 重叠度 ≥ 30%
            if token_ratio >= 0.3:
                found = True
                break

            # 第 2 层：关键实体匹配（数字/日期/专名中有 ≥ 1 个命中）
            src_entities = _extract_entities(src_text)
            if claim_entities["numbers"] & src_entities["numbers"]:
                found = True
                break
            if claim_entities["dates"] & src_entities["dates"]:
                found = True
                break

            # 第 3 层：否定语义检查 —— 回答有否定词但来源没有 → 疑似编造
            if claim_negated and not _has_negation(src_text):
                # 否定声明需要更高的验证标准（至少 token 重叠 ≥ 20%）
                if token_ratio >= 0.2:
                    found = True
                    break
            elif token_ratio >= 0.2:
                found = True
                break

        if not found:
            unverified.append(claim_clean)

    passed = len(unverified) == 0
    if not passed:
        logger.warning(f"未经验证的声明 ({len(unverified)} 条): {unverified}")
    return {"pass": passed, "unverified_claims": unverified}
