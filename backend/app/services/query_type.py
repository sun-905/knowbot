"""
查询类型分类器 —— 三层 TOP-K 方案的在线层

在意图识别之后、查询改写之前调用，根据查询的结构特征将问题分为
"简单事实类"或"复杂类"，从而在 K_floor 和 K_opt 之间选择。

分类规则：
  - 简单事实类：短查询、单一实体、无比较词 → K = K_floor
  - 复杂类：含比较多跳词、长查询 → K = K_opt
  - 兜底：K = K_opt（安全侧）
"""

import re

from loguru import logger

from ..core.config import settings

# 比较 / 多跳关键词
_COMPARISON_PATTERNS = [
    r"(对比|比较|区别|差别|差异|不同|哪个更好|哪个更划算|优缺点|优劣|vs\.?)",
    r"\w+\s*(和|与|跟|同)\s*\w+\s*(哪个|什么区别|有什么不同)",
    r"(分别|各自|分别有|各有什么)",
]

# 复杂分析关键词
_COMPLEX_PATTERNS = [
    r"(为什么|原因|怎么办|如何解决|怎么处理|怎么操作)",
    r"(如果|假如|假设|要是).{2,}(怎么办|会怎样|该如何)",
    r"(流程|步骤|手续|条件|要求).{0,5}(是什么|有哪些|怎样)",
]

# 编译正则
_COMPARISON_RE = [re.compile(p) for p in _COMPARISON_PATTERNS]
_COMPLEX_RE = [re.compile(p) for p in _COMPLEX_PATTERNS]


def classify_query_type(user_message: str) -> str:
    """
    将用户查询分为 'simple' 或 'complex'。

    返回：
        'simple'  → 使用 K_floor（P95+1），省 token
        'complex' → 使用 K_opt（消融最优），保证信息覆盖
    """
    text = user_message.strip()

    # 兜底：空消息 → simple
    if not text:
        return "simple"

    # 规则 1：含比较词 → complex
    for pat in _COMPARISON_RE:
        if pat.search(text):
            logger.debug(f"查询类型=complex（比较词匹配: {pat.pattern[:30]}）")
            return "complex"

    # 规则 2：含复杂分析词 → complex
    for pat in _COMPLEX_RE:
        if pat.search(text):
            logger.debug(f"查询类型=complex（复杂词匹配: {pat.pattern[:30]}）")
            return "complex"

    # 规则 3：长查询（>30 字）更可能包含多跳 → complex
    if len(text) > 30:
        logger.debug(f"查询类型=complex（长度={len(text)}>30）")
        return "complex"

    # 默认 → simple
    logger.debug(f"查询类型=simple（长度={len(text)}，无匹配模式）")
    return "simple"


def get_effective_top_k(user_message: str) -> int:
    """
    根据查询类型返回应使用的 TOP_K 值。

    优先级：
      1. K_floor / K_opt（如果已校准且 > 0）
      2. retrieval_top_k（兜底默认值）
    """
    qtype = classify_query_type(user_message)
    default_k = settings.retrieval_top_k

    if qtype == "simple":
        k = settings.retrieval_top_k_floor or default_k
        if k != default_k:
            logger.debug(f"TOP_K={k} (K_floor, simple query)")
        return k
    else:
        k = settings.retrieval_top_k_opt or default_k
        if k != default_k:
            logger.debug(f"TOP_K={k} (K_opt, complex query)")
        return k
