"""RAG 回答质量评估器 — LLM-as-Judge"""
import json
import re
import os
from typing import Optional

# Judge Prompt
JUDGE_PROMPT = """你是一个严格的 RAG 回答质量评估器。判断 AI 回答是否忠于知识库，不打"人情分"。

【知识库内容（这是唯一的事实来源）】
{knowledge_context}

【用户问题】
{question}

【AI 回答】
{answer}

请逐维度评分（1-5 整数）：

1. 准确性：回答中的每个事实是否能在知识库中找到原文支撑？有没有编造、篡改、添油加醋？
2. 完整性：知识库中与该问题相关的信息，回答是否都覆盖了？
3. 边界遵守：知识库中没有的信息，回答是否明确说"无法确认"？有没有偷偷用常识补充？
4. 简洁性：是否先结论后细节，控制在 300 字以内？
5. 来源引用：关键信息是否标注了【来源：文档名】？

严格按此 JSON 格式返回，不要任何其他内容：
{"accuracy": N, "completeness": N, "boundary": N, "conciseness": N, "citation": N, "reason": "简要理由"}
"""

# 权重
WEIGHTS = {
    "accuracy": 0.40,
    "completeness": 0.25,
    "boundary": 0.20,
    "conciseness": 0.10,
    "citation": 0.05,
}

# 规则断言（不需要 LLM）
HARD_ASSERTIONS: dict = {}

def load_hard_assertions():
    """从 questions.json 加载规则断言"""
    global HARD_ASSERTIONS
    path = os.path.join(os.path.dirname(__file__), "test_datasets", "questions.json")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    for category in data.values():
        for q in category:
            checks = {}
            if q.get("must_contain"):
                checks["must_contain"] = q["must_contain"]
            if q.get("must_not"):
                checks["must_not"] = q["must_not"]
            if checks:
                HARD_ASSERTIONS[q["id"]] = checks


def check_hard_assertions(qid: str, answer: str) -> dict:
    """执行硬断言检查，返回 {passed, checks}"""
    rules = HARD_ASSERTIONS.get(qid, {})
    if not rules:
        return {"passed": True, "checks": []}

    checks = []
    passed = True

    for term in rules.get("must_contain", []):
        ok = term.lower() in answer.lower()
        checks.append(f"must_contain:{term} {'PASS' if ok else 'FAIL'}")
        if not ok:
            passed = False

    for term in rules.get("must_not", []):
        ok = term.lower() not in answer.lower()
        checks.append(f"must_not:{term} {'PASS' if ok else 'FAIL'}")
        if not ok:
            passed = False

    return {"passed": passed, "checks": checks}


def compute_weighted_score(judge_scores: dict) -> float:
    """计算加权总分"""
    return round(sum(
        judge_scores.get(k, 0) * WEIGHTS[k]
        for k in WEIGHTS
    ), 2)


def evaluate_results(results: list[dict]) -> dict:
    """汇总评估结果，返回报告"""
    if not results:
        return {"error": "no results"}

    total = len(results)
    avg_weighted = round(sum(r["weighted"] for r in results) / total, 2)
    avg_accuracy = round(sum(r["judge"]["accuracy"] for r in results) / total, 2)

    # 按类别分组
    by_cat = {}
    for r in results:
        cat = r["id"][0]
        if cat not in by_cat:
            by_cat[cat] = []
        by_cat[cat].append(r)

    categories = {}
    for cat, items in by_cat.items():
        categories[cat] = {
            "count": len(items),
            "avg_weighted": round(sum(i["weighted"] for i in items) / len(items), 2),
        }

    # 一票否决检查
    veto_triggered = False
    veto_reasons = []

    # B 类：无法确认率
    b_items = by_cat.get("B", [])
    if b_items:
        unable_count = sum(1 for i in b_items if any(
            w in i["answer"].lower() for w in ["无法确认", "没有相关", "暂时无法", "未能找到"]
        ))
        unable_rate = unable_count / len(b_items)
        if unable_rate < 0.8:
            veto_triggered = True
            veto_reasons.append(f"B类无法确认率 {unable_rate:.0%} < 80%")

    # 评级
    if avg_weighted >= 4.0 and avg_accuracy >= 4.0 and not veto_triggered:
        rating = "优秀"
    elif avg_weighted >= 3.0 and avg_accuracy >= 3.0:
        rating = "合格"
    else:
        rating = "不合格"

    if veto_triggered and rating != "不合格":
        # 降一级
        if rating == "优秀":
            rating = "合格"
        elif rating == "合格":
            rating = "不合格"

    return {
        "summary": {
            "total_questions": total,
            "average_weighted_score": avg_weighted,
            "average_accuracy": avg_accuracy,
            "rating": rating,
            "veto_triggered": veto_triggered,
            "veto_reasons": veto_reasons,
        },
        "by_category": categories,
        "details": results,
    }


# 启动时加载断言规则
load_hard_assertions()
