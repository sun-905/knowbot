import json
import re
from pathlib import Path

import numpy as np
from loguru import logger

from ..core.config import settings
from ..core.embedding import encode, encode_query
from ..core.llm_client import _get_deepseek

_DATA_DIR = Path(__file__).parent.parent / "data"
_rules: list[dict] = []
_examples: list[dict] = []
_example_embeddings: np.ndarray | None = None


def _load_rules() -> list[dict]:
    """加载意图规则配置"""
    global _rules
    if not _rules:
        path = _DATA_DIR / "intent_rules.json"
        if path.exists():
            _rules = json.loads(path.read_text(encoding="utf-8")).get("rules", [])
            _rules.sort(key=lambda r: r.get("priority", 99))
    return _rules


def _load_examples() -> list[dict]:
    """加载意图示例数据"""
    global _examples
    if not _examples:
        path = _DATA_DIR / "intent_examples.json"
        if path.exists():
            _examples = json.loads(path.read_text(encoding="utf-8")).get("examples", [])
    return _examples


async def _get_example_embeddings() -> np.ndarray:
    """获取或计算示例的向量嵌入"""
    global _example_embeddings
    if _example_embeddings is None:
        examples = _load_examples()
        if examples:
            texts = [e["text"] for e in examples]
            _example_embeddings = await encode(texts)
        else:
            _example_embeddings = np.array([])
    return _example_embeddings


# --- L1: 规则匹配 ---
def _l1_rule_match(text: str) -> dict | None:
    rules = _load_rules()
    text_lower = text.lower()
    for rule in rules:
        for kw in rule.get("keywords", []):
            if kw in text_lower or kw in text:
                return {"intent": rule["intent"], "confidence": 0.95, "source": "rule", "clarify": False}
        for pat in rule.get("patterns", []):
            if re.search(pat, text):
                return {"intent": rule["intent"], "confidence": 0.90, "source": "rule", "clarify": False}
    return None


# --- L2: 向量匹配 ---
async def _l2_vector_match(text: str) -> dict | None:
    examples = _load_examples()
    if not examples:
        return None
    emb = await _get_example_embeddings()
    if emb is None or emb.size == 0:
        return None

    qv = await encode_query(text)
    qv = qv / (np.linalg.norm(qv) + 1e-8)
    emb_norm = emb / (np.linalg.norm(emb, axis=1, keepdims=True) + 1e-8)
    similarities = np.dot(emb_norm, qv)

    top_idx = int(np.argmax(similarities))
    top_score = float(similarities[top_idx])

    if top_score > 0.80:
        return {"intent": examples[top_idx]["intent"], "confidence": round(top_score, 2), "source": "vector", "clarify": False}
    return None


# --- L3: 大模型分类 ---
async def _l3_llm_classify(text: str, history_context: str = "") -> dict:
    client = _get_deepseek()
    system_prompt = (
        "你是一个意图分类器。将用户消息归入以下类别之一："
        "产品咨询、售后问题、订单查询、账号问题、投诉、闲聊、其他。"
        "只返回 JSON：{\"intent\": \"...\", \"confidence\": 0.0-1.0}"
    )
    user_msg = f"用户消息：{text}"
    if history_context:
        user_msg = f"对话历史：{history_context}\n{user_msg}"

    try:
        response = await client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg},
            ],
            temperature=0,
            max_tokens=100,
        )
        raw = response.choices[0].message.content.strip()
        # 提取 JSON
        import re as _re
        match = _re.search(r"\{[^}]+\}", raw)
        if match:
            result = json.loads(match.group())
            confidence = float(result.get("confidence", 0.5))
            return {"intent": result.get("intent", "其他"), "confidence": confidence, "source": "llm", "clarify": confidence < settings.intent_clarify_threshold}
    except Exception as e:
        logger.warning(f"LLM 意图分类失败: {e}")

    return {"intent": "其他", "confidence": 0.5, "source": "llm", "clarify": False}


# --- 主入口 ---
async def classify_intent(text: str, history_context: str = "") -> dict:
    """三级意图分类：规则 → 向量 → 大模型"""
    # L1: 规则匹配
    result = _l1_rule_match(text)
    if result:
        logger.info(f"意图(L1-规则): {result['intent']} ({result['confidence']})")
        return result

    # L2: 向量匹配
    result = await _l2_vector_match(text)
    if result:
        logger.info(f"意图(L2-向量): {result['intent']} ({result['confidence']})")
        return result

    # L3: 大模型
    result = await _l3_llm_classify(text, history_context)
    logger.info(f"意图(L3-大模型): {result['intent']} ({result['confidence']}) 追问={result.get('clarify')}")
    return result
