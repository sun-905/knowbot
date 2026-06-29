"""RAG 质量评估 — 规则断言（不需要 LLM，秒级执行）

前置条件：测试文档已入库到知识库
"""
import pytest
import json
import os
import asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app
from tests.rag_eval.judge import check_hard_assertions, compute_weighted_score, evaluate_results


DATASET_DIR = os.path.join(os.path.dirname(__file__), "test_datasets")


def load_questions():
    path = os.path.join(DATASET_DIR, "questions.json")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    all_qs = []
    for cat, qs in data.items():
        for q in qs:
            q["category"] = cat
            all_qs.append(q)
    return all_qs


async def ask_question(client: AsyncClient, question: str, token: str) -> str:
    """发送问题到 RAG 系统，收集完整回答"""
    # 创建会话
    resp = await client.post("/sessions", json={"title": "eval"}, headers={"Authorization": f"Bearer {token}"})
    session_id = resp.json()["id"]

    # 发送问题
    resp2 = await client.post(
        f"/sessions/{session_id}/chat",
        json={"content": question},
        headers={"Authorization": f"Bearer {token}"},
        timeout=60.0,
    )
    # 从 SSE 流中提取 delta 内容
    answer_parts = []
    for line in resp2.text.split("\n"):
        if line.startswith("data: "):
            data = line[6:].strip()
            try:
                obj = json.loads(data)
                if "content" in obj:
                    answer_parts.append(obj["content"])
            except (json.JSONDecodeError, TypeError):
                pass
    return "".join(answer_parts)


@pytest.mark.asyncio
async def test_all_hard_assertions():
    """对全部 20 题执行规则断言检查"""
    # 注册测试用户
    import uuid
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        phone = f"130{str(uuid.uuid4().int)[-8:]}"
        resp = await client.post("/auth/register", json={
            "phone": phone, "password": "eval123456", "nickname": "eval-user",
        })
        assert resp.status_code == 201, f"注册失败: {resp.text}"
        resp2 = await client.post("/auth/login", json={"account": phone, "password": "eval123456"})
        assert resp2.status_code == 200, f"登录失败: {resp2.text}"
        token = resp2.json()["access_token"]

        questions = load_questions()
        results = []

        for q in questions:
            qid = q["id"]
            question = q["question"]

            answer = await ask_question(client, question, token)

            # 规则断言
            hard = check_hard_assertions(qid, answer)
            status = "PASS" if hard["passed"] else "FAIL"
            # 避免中文打印导致的 GBK 编码错误
            print(f"[{qid}] {status} | {question[:40]} | answer_snippet={answer[:80]}")

            results.append({
                "id": qid,
                "category": q["category"],
                "question": question,
                "answer": answer,
                "hard_assertions": hard,
                "judge": {"accuracy": 5 if hard["passed"] else 1, "completeness": 3, "boundary": 3, "conciseness": 3, "citation": 3},
                "weighted": 5.0 if hard["passed"] else 1.0,
            })

        # 汇总
        report = evaluate_results(results)
        passed = sum(1 for r in results if r['hard_assertions']['passed'])
        print(f"TOTAL: {passed}/{len(results)} hard assertions passed")
        print(f"Rating: {report['summary']['rating']}")

        # 保存报告
        report_path = os.path.join(os.path.dirname(__file__), "eval_report.json")
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"  报告已保存: {report_path}")

        # B 类必须全部通过（无法确认）
        b_results = [r for r in results if r["category"] == "B"]
        b_pass = sum(1 for r in b_results if r["hard_assertions"]["passed"])
        assert b_pass >= 4, f"B 类边界测试: {b_pass}/{len(b_results)} 通过（需要 >=4）"

        # A 类至少 80% 通过
        a_results = [r for r in results if r["category"] == "A"]
        a_pass = sum(1 for r in a_results if r["hard_assertions"]["passed"])
        assert a_pass >= 8, f"A 类准确性测试: {a_pass}/{len(a_results)} 通过（需要 >=8）"
