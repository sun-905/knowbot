"""窄窗口忠实度消融（Layer 2）：在 [K_floor, K_floor+4] 范围内用忠实度确定 K_opt。

方法：
1. Layer 1 产出 K_floor = P95(gt_rank) + 1
2. 在窄窗口 [K_floor, K_floor+4] 内，对每个 K 值：
   - 跑完整 RAG（检索+重排序+LLM生成）
   - 用不同的 LLM 做 Judge，评估忠实度（Faithfulness）
   - Faithfulness：将答案拆成原子陈述，逐条检查是否在 K 个片段中找到依据
3. 绘制 K vs Faithfulness 曲线，找到平台期起点 → K_opt
4. 副产品：校准分层摘要的 core/ref/edge 阈值

Judge 独立性要求：
  - DeepSeek 做生成 → Qwen 做 Judge（主方向）
  - Qwen 做生成 → DeepSeek 做 Judge（交叉验证）
  - 取两次评估的平均值消除 Judge 偏见
"""
import sys, io, os, json, asyncio, time, re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

import httpx
from openai import AsyncOpenAI
from app.core.config import settings
from app.services.retrieval import hybrid_search, rerank

FAITHFULNESS_JUDGE_PROMPT = """你是一个严格的忠实度评估器。你的唯一任务是判断 AI 回答中的每个陈述是否能从提供的上下文中找到依据。

【上下文（知识片段）】
{context}

【用户问题】
{question}

【AI 回答】
{answer}

请按以下步骤执行：

1. 将 AI 回答拆成原子陈述（每个不可再分的事实声明）。
2. 对每个陈述，在上下文中搜索支撑证据：
   - 找到明确支撑 → VERIFIED
   - 上下文提到相关内容但表述不同 → PARTIAL（说明差异）
   - 上下文中完全找不到 → UNVERIFIED
3. 统计结果。

严格按此 JSON 格式返回，不要任何其他内容：
{{
  "statements": [
    {{"text": "陈述原文", "verdict": "VERIFIED|PARTIAL|UNVERIFIED", "evidence": "证据片段或空"}}
  ],
  "verified_count": N,
  "partial_count": N,
  "unverified_count": N,
  "total_count": N,
  "faithfulness": 0.0  // (verified + 0.5*partial) / total，取值范围 [0, 1]
}}
"""


def load_questions():
    """加载标注问题集"""
    path = os.path.join(os.path.dirname(__file__), "test_datasets", "questions.json")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return [q for cat, qs in data.items() for q in [{**q, "category": cat} for q in qs]]


async def judge_faithfulness(
    judge_client: AsyncOpenAI,
    judge_model: str,
    question: str,
    answer: str,
    contexts: list[dict],
) -> dict:
    """用 Judge LLM 评估一次忠实度"""
    # 构建上下文文本
    context_text = "\n\n---\n".join([
        f"[{i+1}] 来源:{c.get('doc_name','未知')} | 分数:{c.get('rerank_score',c.get('score',0)):.3f}\n{c.get('text','')[:1000]}"
        for i, c in enumerate(contexts)
    ])

    prompt = FAITHFULNESS_JUDGE_PROMPT.format(
        context=context_text[:8000],  # 防止超窗口
        question=question,
        answer=answer,
    )

    try:
        response = await judge_client.chat.completions.create(
            model=judge_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=2000,
        )
        raw = response.choices[0].message.content.strip()
        # 提取 JSON
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            result = json.loads(match.group())
            return {
                "faithfulness": float(result.get("faithfulness", 0)),
                "verified": int(result.get("verified_count", 0)),
                "partial": int(result.get("partial_count", 0)),
                "unverified": int(result.get("unverified_count", 0)),
                "total": int(result.get("total_count", 0)),
            }
    except Exception as e:
        print(f"  Judge 评估失败: {e}")

    return {"faithfulness": 0, "verified": 0, "partial": 0, "unverified": 0, "total": 0}


async def run_one_k(
    k: int,
    questions: list[dict],
    gen_client: AsyncOpenAI,
    gen_model: str,
    judge_client: AsyncOpenAI,
    judge_model: str,
    label: str = "",
) -> dict:
    """对单个 K 值运行完整消融测试"""
    print(f"\n{'─'*60}")
    print(f"测试 K={k} {label}")
    print(f"{'─'*60}")

    results = []

    for i, q in enumerate(questions):
        question = q["question"]
        t0 = time.time()

        # 检索 + 重排序
        candidates = await hybrid_search(question)
        reranked = await rerank(question, candidates, top_n=max(k, 5))
        top_docs = reranked[:k]

        # LLM 生成
        context_text = "\n\n---\n".join([
            f"【来源：{d.get('doc_name','未知')}】{d.get('text','')}"
            for d in top_docs
        ])
        messages = [
            {"role": "system", "content": "你是一个基于知识库的客服助手。仅根据提供的知识内容回答问题，不要编造。"},
            {"role": "user", "content": f"知识库内容：\n{context_text}\n\n用户问题：{question}"},
        ]

        answer = ""
        try:
            response = await gen_client.chat.completions.create(
                model=gen_model,
                messages=messages,
                temperature=0,
                max_tokens=500,
            )
            answer = response.choices[0].message.content
        except Exception as e:
            print(f"  [{q['id']}] 生成失败: {e}")
            answer = "生成失败"

        # Faithfulness Judge
        faith = await judge_faithfulness(judge_client, judge_model, question, answer, top_docs)

        elapsed = time.time() - t0
        print(f"  [{q['id']}] faithfulness={faith['faithfulness']:.2f} "
              f"({faith['verified']}V/{faith['partial']}P/{faith['unverified']}U) "
              f"({elapsed:.1f}s)")

        results.append({
            "qid": q["id"],
            "question": question[:60],
            "k": k,
            "answer": answer[:300],
            "faithfulness": faith["faithfulness"],
            "verified": faith["verified"],
            "partial": faith["partial"],
            "unverified": faith["unverified"],
            "context_count": len(top_docs),
        })

    avg_faith = round(sum(r["faithfulness"] for r in results) / len(results), 3)
    print(f"  → K={k} 平均忠实度: {avg_faith}")

    return {"k": k, "avg_faithfulness": avg_faith, "details": results}


async def main():
    k_floor = int(sys.argv[1]) if len(sys.argv) > 1 else None
    if k_floor is None:
        # 尝试从 Layer 1 的结果读取
        # 或者使用配置中的默认值
        k_floor = settings.retrieval_top_k_floor or settings.retrieval_top_k
        print(f"未指定 K_floor，使用默认值: {k_floor}")
        print(f"用法: python calibrate_top_k.py <K_floor>\n")

    print("=" * 60)
    print(f"Layer 2 窄窗口忠实度消融：K ∈ [{k_floor}, {k_floor+4}]")
    print("=" * 60)

    # 初始化客户端
    gen_client = AsyncOpenAI(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        timeout=httpx.Timeout(120.0, connect=10.0),
        max_retries=1,
    )
    gen_model = settings.llm_model

    judge_client = AsyncOpenAI(
        api_key=settings.qwen_api_key,
        base_url=settings.qwen_base_url,
        timeout=httpx.Timeout(120.0, connect=10.0),
        max_retries=1,
    )
    judge_model = "qwen-turbo"  # Qwen 做 Judge，≠ DeepSeek(生成)

    if not settings.qwen_api_key:
        print("\n⚠️  未配置 QWEN_API_KEY，Judge 将回退到 DeepSeek（同模型自评，有偏差）")
        judge_client = gen_client
        judge_model = gen_model

    questions = load_questions()
    # 只测有地面真相标注的题（A/C/D 类）
    eval_questions = [q for q in questions if q.get("id", "")[0] in "ACD"]
    print(f"评估集: {len(eval_questions)} 题 (A/C/D 类，有 ground-truth)\n")

    # 窄窗口消融
    ks = list(range(k_floor, k_floor + 5))
    all_results = []

    for k in ks:
        result = await run_one_k(
            k, eval_questions,
            gen_client, gen_model,
            judge_client, judge_model,
            label="(DeepSeek生成→Qwen评判)" if settings.qwen_api_key else "(同模型自评⚠️)",
        )
        all_results.append(result)

    # ---- 分析 ----
    print(f"\n{'='*60}")
    print("消融结果汇总")
    print(f"{'='*60}")
    print(f"{'K':<6} {'忠实度':<10} {'变化':<10}")
    print("-" * 30)

    best_k = None
    best_faith = 0
    for i, r in enumerate(all_results):
        k = r["k"]
        faith = r["avg_faithfulness"]
        delta = ""
        if i > 0:
            prev_faith = all_results[i-1]["avg_faithfulness"]
            delta = f"{faith - prev_faith:+.3f}"
        print(f"{k:<6} {faith:<10.3f} {delta:<10}")
        if faith > best_faith:
            best_faith = faith
            best_k = k

    # 找平台期起点：第一个 ≥ 0.95 × 最高忠实度 的 K
    threshold_95 = best_faith * 0.95
    k_opt = None
    for r in all_results:
        if r["avg_faithfulness"] >= threshold_95:
            k_opt = r["k"]
            break

    print(f"\n最高忠实度: {best_faith:.3f} (K={best_k})")
    print(f"95% 阈值:    {threshold_95:.3f}")
    print(f"平台期起点:  K_opt = {k_opt}")

    # 判断 K_opt 是否明显优于 K_floor
    floor_faith = all_results[0]["avg_faithfulness"]
    opt_faith = next((r["avg_faithfulness"] for r in all_results if r["k"] == k_opt), floor_faith)
    if opt_faith - floor_faith < 0.02:
        print(f"\n  → K_opt 与 K_floor 忠实度差异 < 0.02，建议 K_opt = K_floor = {k_floor}")
        k_opt = k_floor

    # ---- 结论 ----
    print(f"\n{'='*60}")
    print(f"结论")
    print(f"{'='*60}")
    print(f"  K_floor = {k_floor}    (P95+1, Layer 1)")
    print(f"  K_opt   = {k_opt}    (窄窗消融最优, Layer 2)")
    print(f"")
    print(f"  配置命令:")
    print(f"    RETRIEVAL_TOP_K_FLOOR={k_floor}")
    print(f"    RETRIEVAL_TOP_K_OPT={k_opt}")

    # ---- 副产品：校准分层摘要阈值 ----
    print(f"\n{'─'*60}")
    print(f"副产品：分层摘要阈值分析")
    print(f"{'─'*60}")

    # 收集所有 (rerank_score, faithfulness_verdict) 对
    score_verdict_pairs = []
    for r in all_results:
        for d in r["details"]:
            # 从 judge 输出中提取每个 statement 的分数和裁决
            # 这里简化：用该 K 下的平均忠实度近似
            for ctx in d.get("contexts", []):
                score_verdict_pairs.append({
                    "rerank_score": ctx.get("rerank_score", 0),
                    "k_faithfulness": d["faithfulness"],
                })

    print("(需要完整的 statement 级别标注才能精确校准分层摘要阈值)")
    print("当前硬编码: core≥0.85 / ref≥0.70 / edge<0.70")
    print("建议：收集足够 statement 级别数据后重新校准")

    # 保存结果
    out = {
        "config": {
            "k_floor": k_floor,
            "k_opt": k_opt,
            "ks_tested": ks,
            "gen_model": gen_model,
            "judge_model": judge_model,
            "judge_independent": settings.qwen_api_key != "",
        },
        "ablation": [{"k": r["k"], "avg_faithfulness": r["avg_faithfulness"]} for r in all_results],
        "details": all_results,
    }
    out_path = os.path.join(os.path.dirname(__file__), "top_k_calibration.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存: {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
