"""纯检索扫描（Layer 1）：不调 LLM，只统计 ground-truth 文档在两个节点的数据。

节点 1：混合检索后 20 条候选的最高原始分数 → 决定 THRESHOLD（安全区间法）
节点 2：重排序后 ground-truth 的排名 → P95(gt_rank)+1 = K_floor

变更（v2）：TOP_K 从 max(gt_rank)+2 改为 P95(gt_rank)+1
  - P95 比 max 更鲁棒，不会因单个 outlier 绑架全部题的上下文大小
  - +1 余量在 P95 下足够（P95 本身已去掉了 5% 的 tail）
"""
import sys, io, os, json, asyncio, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

from app.services.retrieval import hybrid_search, rerank

# 每题对应的 ground-truth 文档名关键词
GROUND_TRUTH = {
    "A1": ["产品手册"], "A2": ["售后政策"], "A3": ["售后政策"],
    "A4": ["退换货"], "A5": ["售后政策"],
    "A6": ["会员权益"], "A7": ["产品手册"], "A8": ["售后政策"],
    "A9": ["常见问题"], "A10": ["会员权益"],
    "B1": None, "B2": None, "B3": None, "B4": None, "B5": ["退换货"],
    "C1": ["售后政策"], "C2": ["产品手册"], "C3": ["会员权益"],
    "D1": ["产品手册"], "D2": ["售后政策"],
}

QUESTIONS = {
    "A1": "智能门锁 X1 多少钱？", "A2": "退货需要在几天内申请？",
    "A3": "换货期限是多久？", "A4": "如何申请退货？",
    "A5": "保修期多长？", "A6": "钻石会员有什么权益？",
    "A7": "X3 支持哪些开锁方式？", "A8": "退货需要什么条件？",
    "A9": "如何查询物流？", "A10": "银卡会员的积分倍率是多少？",
    "B1": "产品 X5 多少钱？", "B2": "可以退货到海外地址吗？",
    "B3": "CEO 是谁？", "B4": "有没有实体门店？",
    "B5": "退款多久到账？",
    "C1": "退货期限一般是多久？", "C2": "有哪些品牌的智能门锁？",
    "C3": "会员怎么升级？",
    "D1": "X2 和 X3 哪个性价比更高？", "D2": "退货和换货分别有什么要求？",
}


async def main():
    print("=" * 70)
    print("纯检索扫描：ground-truth 在检索管线中的表现")
    print("=" * 70)

    results = []

    for qid, question in QUESTIONS.items():
        gt_docs = GROUND_TRUTH.get(qid)
        has_gt = gt_docs is not None

        t0 = time.time()

        # 节点 1：混合检索
        candidates = await hybrid_search(question)

        # 记录最高原始分数
        max_raw = max((c.get("score", 0) for c in candidates), default=0)

        # 节点 2：重排序
        reranked = await rerank(question, candidates, top_n=20)

        # 找 ground-truth 文档在重排序后的排名
        gt_ranks = []
        for gt in (gt_docs or []):
            for rank, doc in enumerate(reranked, 1):
                if gt in doc.get("doc_name", ""):
                    gt_ranks.append(rank)
                    break
            else:
                gt_ranks.append(None)  # 没找到

        elapsed = time.time() - t0

        row = {
            "qid": qid,
            "question": question[:30],
            "has_gt": has_gt,
            "gt_docs": gt_docs,
            "max_raw_score": round(max_raw, 4),
            "gt_rank_after_rerank": gt_ranks if gt_ranks else None,
            "candidate_count": len(candidates),
        }
        results.append(row)

        gt_str = f"gt_rank={gt_ranks}" if has_gt else "gt=None"
        print(f"[{qid}] max_raw={max_raw:.4f}  {gt_str}  ({elapsed:.1f}s)")

    # ---- 分析 ----
    print("\n" + "=" * 70)
    print("分析")
    print("=" * 70)

    # 有 ground-truth 的题目
    with_gt = [r for r in results if r["has_gt"]]
    without_gt = [r for r in results if not r["has_gt"]]

    # threshold 上限 = min(所有有 gt 题目的 max_raw_score)
    # 如果 threshold > 某题 max_raw，该题会被误杀
    if with_gt:
        min_max_raw = min(r["max_raw_score"] for r in with_gt)
        max_max_raw_no_gt = max((r["max_raw_score"] for r in without_gt), default=0)

        print(f"\n--- RETRIEVAL_THRESHOLD ---")
        print(f"有答案题目中，最低的 max_raw = {min_max_raw:.4f}")
        print(f"  含义：threshold 必须 ≤ {min_max_raw:.4f}，否则该题会被误拦")
        for r in with_gt:
            if r["max_raw_score"] == min_max_raw:
                print(f"  临界题: [{r['qid']}] {r['question']} (max_raw={r['max_raw_score']:.4f})")

        print(f"\n无答案题目中，最高的 max_raw = {max_max_raw_no_gt:.4f}")
        print(f"  含义：threshold 最好 > {max_max_raw_no_gt:.4f}，否则这些题拦不住")
        if max_max_raw_no_gt > 0:
            for r in without_gt:
                print(f"  [{r['qid']}] {r['question']} (max_raw={r['max_raw_score']:.4f})")

        if max_max_raw_no_gt < min_max_raw:
            gap = min_max_raw - max_max_raw_no_gt
            print(f"\n  ✅ 安全区间存在：({max_max_raw_no_gt:.4f}, {min_max_raw:.4f}]")
            print(f"     间隔宽度 = {gap:.4f}")
            print(f"     推荐 threshold = {round((max_max_raw_no_gt + min_max_raw) / 2, 2):.2f}")
        else:
            print(f"\n  ❌ 无安全区间！有答案的最低分 ≤ 无答案的最高分")
            print(f"     无论设什么阈值都会产生误判")

    # top_k 下限 = P95(gt_rank) + 1
    # P95 比 max 更鲁棒——单个 outlier 不会绑架整个结论
    all_ranks = []
    for r in with_gt:
        ranks = r.get("gt_rank_after_rerank") or []
        for rank in ranks:
            if rank is not None:
                all_ranks.append((r["qid"], rank))

    print(f"\n--- RETRIEVAL_TOP_K ---")
    if all_ranks:
        max_rank = max(r for _, r in all_ranks)
        sorted_ranks = sorted([r for _, r in all_ranks])
        n = len(sorted_ranks)
        # P95: 第 95 百分位的排名
        p95_idx = int(n * 0.95) if n >= 20 else n - 1  # 小样本退化为 max
        p95_rank = sorted_ranks[p95_idx]

        print(f"ground-truth 排名分布: {sorted_ranks}")
        print(f"  max  = {max_rank}  (会被 1 个 outlier 绑架)")
        print(f"  P95  = {p95_rank}   (覆盖 {min(95, int(p95_idx/n*100))}% 的问题)")
        print(f"  P50  = {sorted_ranks[n//2]}   (中位数)")

        k_floor = p95_rank + 1
        print(f"\n  推荐 K_floor = P95 + 1 = {k_floor}")
        print(f"    含义：{k_floor} 条文档覆盖了 ≥95% 问题的正确答案")
        print(f"    如需鲁棒性，可设 K_opt = K_floor + 2 = {k_floor + 2}（待第二层消融确认）")

        # 用 max 方法做对比
        old_k = max_rank + 2
        print(f"\n  对比旧方案 (max+2): K = {old_k}")
        if k_floor < old_k:
            print(f"    → 新方案节省 {old_k - k_floor} 条上下文 (~{(old_k - k_floor) * 200} tokens/次)")
    else:
        k_floor = 5
        print("无 ground-truth 排名数据，保持默认 K_floor = 5")

    # 汇总
    print(f"\n{'='*70}")
    print(f"结论:")
    if with_gt and without_gt:
        max_max_raw_no_gt = max((r["max_raw_score"] for r in without_gt), default=0)
        min_max_raw = min(r["max_raw_score"] for r in with_gt)
        if max_max_raw_no_gt < min_max_raw:
            rec_threshold = round((max_max_raw_no_gt + min_max_raw) / 2, 2)
        else:
            rec_threshold = round(min_max_raw, 2)
    else:
        rec_threshold = 0.43
    print(f"  RETRIEVAL_THRESHOLD = {rec_threshold:.2f}")
    print(f"  RETRIEVAL_TOP_K_FLOOR = {k_floor}")


if __name__ == "__main__":
    asyncio.run(main())
