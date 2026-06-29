import asyncio
import json
from collections.abc import AsyncGenerator
from datetime import datetime, timezone, timedelta

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..core.llm_client import chat_stream_with_fallback
from ..models.message import Message
from ..models.session import Session
from .context_guard import stratified_summarize, prioritize_by_type, verify_answer
from .intent import classify_intent
from .query_rewriter import rewrite_query
from .query_type import get_effective_top_k
from .retrieval import hybrid_search, rerank

SYSTEM_PROMPT = """你是一个基于知识库的 AI 客服助手。你的所有知识来自系统提供的知识库文档，你不代表任何具体公司，也不知道任何公司的内部信息。请严格遵循以下规则：

【信息边界 — 最高优先级】
1. 仅根据提供的「知识库内容」回答问题。知识库中没有的信息，你必须明确说"根据现有资料，我无法确认..."，绝对不要猜测或编造。
2. 如果知识库内容之间存在矛盾，请指出矛盾之处，不要擅自选择其一。
3. 禁止使用你的训练数据或常识来补充知识库中不存在的信息。即使你认为某件事"应该是这样"，只要知识库里没有，就不能说。
4. 关于公司内部信息（CEO是谁、员工姓名、组织架构、公司地址等），除非知识库中明确记载，否则你必须回答"根据现有资料，我无法确认"。不要扮演"公司员工"角色来编造这类信息。

【回答格式】
5. 回答结构：先给出直接结论，再展开说明细节。
6. 引用来源时用【来源：文档名】标注。如多个来源说法一致，合并引用。

【安全约束】
7. 涉及法律、财务、医疗建议时，必须在回答末尾加"建议您进一步咨询相关专业人士"。
8. 用户提出投诉时，先表达理解和歉意，再给出解决方案。

【输出控制】
9. 回答简洁，控制在 300 字以内（除非用户明确要求详细）。
10. 使用 Markdown 优化可读性。

【反幻觉示例】
❌ 知识库只有"产品A售价100元" → 问"产品B多少钱" → 答"产品B售价200元"（编造）
✅ 知识库只有"产品A售价100元" → 问"产品B多少钱" → 答"根据现有资料，我无法确认产品B的价格"
❌ 知识库说"退货期限7天" → 答"退货期限一般是7-14天"（用常识补充知识库没有的"14天"）
✅ 知识库说"退货期限7天" → 答"根据现有资料，退货期限为7天"
❌ 知识库无CEO信息 → 问"CEO是谁" → 答"CEO是张某某，他是一位有远见的..."（扮演角色编造）
✅ 知识库无CEO信息 → 问"CEO是谁" → 答"根据现有资料，我无法确认该信息" """

CASUAL_SYSTEM_PROMPT = """你是一个基于知识库的 AI 客服助手。用户正在与你闲聊。

重要提醒：你不知道公司的内部信息（CEO、员工、地址等），除非对方明确询问的是知识库中已有的产品/服务问题。闲聊时不要编造任何关于"公司"的具体信息。

你可以：
1. 自然地介绍自己：你是 AI 客服助手，可以帮用户解答产品问题、查询订单、处理售后等。
2. 友好地回应问候和闲聊话题。
3. 如果对方问到你不知道的信息，诚实地说"这个我不太清楚，建议您咨询人工客服"。

保持简短、亲切、有人情味的回复。"""

FALLBACK_REPLY = "抱歉，我暂时无法回答这个问题。建议您联系人工客服获取帮助。"

# 中国标准时间 (UTC+8)
CST = timezone(timedelta(hours=8))


async def get_history(db: AsyncSession, session_id: int, rounds: int = 5) -> list[dict]:
    """获取最近 N 轮对话历史"""
    result = await db.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at.desc())
        .limit(rounds * 2)  # 用户 + 助手 = 每轮 2 条
    )
    messages = result.scalars().all()
    return [
        {"role": m.role, "content": m.content}
        for m in reversed(messages)
    ]


FOLLOWUP_SYSTEM_PROMPT = """你是一个客服追问建议生成器。根据用户的问题、AI 的回答以及知识库内容，生成 3 条用户可以继续追问的实用建议。

规则：
1. 追问建议必须能从知识库中找到答案（不要提知识库覆盖不到的问题）
2. 追问建议要与当前话题紧密相关，自然的下一步问题
3. 每条追问建议不超过 20 个字
4. 优先提供"怎么做"、"需要什么"、"多长时间"等有明确答案的问题
5. 回复格式：每行一个追问建议，只输出 3 行，不要编号，不要任何其他内容"""


async def generate_followups(user_msg: str, answer: str, knowledge_docs: list[dict] | None = None) -> list[str]:
    """根据知识库内容生成追问建议"""
    # 如果没有知识库文档，降级为基础追问
    if not knowledge_docs:
        return ["讲一个冷笑话吧", "今天是什么日子？"]

    # 提取知识库文档摘要（控制长度避免 token 浪费）
    doc_summaries: list[str] = []
    total_chars = 0
    for d in knowledge_docs:
        doc_name = d.get("doc_name", "未知")
        text = d.get("text", "")[:200]  # 每篇最多取 200 字
        if text:
            doc_summaries.append(f"【{doc_name}】{text}")
            total_chars += len(text)
            if total_chars > 1200:  # 控制总长度
                break

    if not doc_summaries:
        return ["讲一个冷笑话吧", "今天是什么日子？"]

    knowledge_snippet = "\n".join(doc_summaries)

    messages = [
        {"role": "system", "content": FOLLOWUP_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"用户问题：{user_msg}\n"
                f"AI 回答概要：{answer[:200]}\n"
                f"知识库内容：\n{knowledge_snippet}\n"
                f"请生成 3 条追问建议："
            ),
        },
    ]

    try:
        from ..core.llm_client import chat_stream_with_fallback
        full = ""
        # 追问 LLM 调用最多等 3 秒，超时则降级
        async def _collect() -> str:
            result = ""
            async for token in chat_stream_with_fallback(messages):
                result += token
            return result
        full = await asyncio.wait_for(_collect(), timeout=3.0)
        # 按行解析，过滤空行，取前 3 条
        lines = [line.strip() for line in full.strip().split("\n") if line.strip()]
        suggestions = [line for line in lines if not line.startswith("#") and len(line) > 2][:3]
        if suggestions:
            return suggestions
    except (Exception, asyncio.TimeoutError) as e:
        logger.warning(f"追问建议生成失败，使用降级策略: {e}")

    return ["还有其他问题吗？", "需要转接人工客服吗？"]


async def rag_chat_stream(
    db: AsyncSession,
    session_id: int,
    user_id: int,
    user_message: str,
    kb_id: int | None = None,
) -> AsyncGenerator[str, None]:
    """RAG 对话流主流程。kb_id 为 None 时查全部知识库。"""
    import time
    t_start = time.time()

    # 1. 意图识别
    intent_result = await classify_intent(user_message)
    yield {"event": "intent", "data": json.dumps(intent_result, ensure_ascii=False)}
    logger.info(f"[{session_id}] 意图: {intent_result['intent']} ({intent_result['source']}) 耗时 {time.time()-t_start:.2f}s")

    # 如果需要追问澄清
    if intent_result.get("clarify"):
        clarify_q = _get_clarify_question(user_message, intent_result)
        # 保存用户消息和澄清回复
        user_msg_obj = Message(session_id=session_id, role="user", content=user_message, intent=f"{intent_result['intent']}|{intent_result['source']}|{intent_result['confidence']}")
        ai_msg_obj = Message(session_id=session_id, role="assistant", content=clarify_q, references_json=[], token_count=len(clarify_q) // 2)
        db.add_all([user_msg_obj, ai_msg_obj])
        yield {"event": "delta", "data": json.dumps({'content': clarify_q}, ensure_ascii=False)}
        yield {"event": "done", "data": json.dumps({'message_id': ai_msg_obj.id}, ensure_ascii=False)}
        return

    # 闲聊意图：跳过检索，直接自由对话
    if intent_result["intent"] == "闲聊":
        history = await get_history(db, session_id, settings.max_context_rounds)
        now = datetime.now(tz=CST)
        weekday = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][now.weekday()]
        today_str = f"{now.year}年{now.month}月{now.day}日 {weekday}"
        messages = [{"role": "system", "content": CASUAL_SYSTEM_PROMPT}]
        for h in history:
            messages.append({"role": h["role"], "content": h["content"]})
        # 日期作为独立 system 消息，紧邻用户问题，LLM 无法忽略
        messages.append({"role": "system", "content": f"现在是{today_str}。回答任何日期时间问题都必须以此为准，即使历史记录中有不同的日期也要以此覆盖。"})
        messages.append({"role": "user", "content": user_message})

        full_answer = ""
        try:
            async for token in chat_stream_with_fallback(messages):
                full_answer += token
                yield {"event": "delta", "data": json.dumps({'content': token}, ensure_ascii=False)}
        except Exception as e:
            logger.error(f"[{session_id}] 闲聊 LLM 生成失败: {e}")
            full_answer = FALLBACK_REPLY
            # 保存用户消息和兜底回复
            user_msg_obj = Message(session_id=session_id, role="user", content=user_message, intent=f"闲聊|{intent_result['source']}|{intent_result['confidence']}")
            ai_msg_obj = Message(session_id=session_id, role="assistant", content=full_answer, references_json=[], token_count=len(full_answer) // 2)
            db.add_all([user_msg_obj, ai_msg_obj])
            yield {"event": "delta", "data": json.dumps({'content': full_answer}, ensure_ascii=False)}
            yield {"event": "done", "data": json.dumps({'message_id': ai_msg_obj.id}, ensure_ascii=False)}
            return

        # 保存消息
        user_msg_obj = Message(session_id=session_id, role="user", content=user_message, intent=f"闲聊|{intent_result['source']}|{intent_result['confidence']}")
        ai_msg_obj = Message(session_id=session_id, role="assistant", content=full_answer, references_json=[], token_count=len(full_answer) // 2)
        db.add_all([user_msg_obj, ai_msg_obj])

        # 如果是首条消息，更新会话标题
        result = await db.execute(select(Message).where(Message.session_id == session_id).limit(1))
        first_msg = result.scalar_one_or_none()
        if first_msg is None or first_msg.id == user_msg_obj.id:
            title = user_message[:30] + ("..." if len(user_message) > 30 else "")
            await db.execute(
                __import__("sqlalchemy").update(Session).where(Session.id == session_id).values(title=title)
            )

        followups = ["讲一个冷笑话吧", "今天是什么日子？"]
        yield {"event": "followups", "data": json.dumps(followups, ensure_ascii=False)}
        yield {"event": "done", "data": json.dumps({'message_id': ai_msg_obj.id}, ensure_ascii=False)}
        logger.info(f"[{session_id}] 闲聊完成 总耗时 {time.time()-t_start:.2f}s")
        return

    # 2. 查询改写：将口语化表达转为专业检索查询
    retrieval_query = user_message
    try:
        retrieval_query = await rewrite_query(user_message, intent_result.get("intent", ""))
        if retrieval_query != user_message:
            yield {"event": "rewritten_query", "data": json.dumps(
                {"original": user_message, "rewritten": retrieval_query}, ensure_ascii=False
            )}
            logger.info(f"[{session_id}] 查询改写: 「{user_message[:40]}」→「{retrieval_query[:60]}」")
    except Exception as e:
        logger.warning(f"[{session_id}] 查询改写异常，使用原始查询: {e}")
        retrieval_query = user_message

    # 3. 混合检索
    yield {"event": "processing", "data": json.dumps({"stage": "检索中"}, ensure_ascii=False)}
    try:
        candidates = await hybrid_search(retrieval_query, kb_id=kb_id)
    except Exception as e:
        logger.error(f"[{session_id}] 混合检索异常: {e}")
        # 检索异常时保存兜底消息，避免历史断裂
        user_msg_obj = Message(session_id=session_id, role="user", content=user_message, intent=f"{intent_result['intent']}|{intent_result['source']}|{intent_result['confidence']}")
        ai_msg_obj = Message(session_id=session_id, role="assistant", content=FALLBACK_REPLY, references_json=[], token_count=len(FALLBACK_REPLY) // 2)
        db.add_all([user_msg_obj, ai_msg_obj])
        yield {"event": "delta", "data": json.dumps({'content': FALLBACK_REPLY}, ensure_ascii=False)}
        yield {"event": "done", "data": json.dumps({'message_id': ai_msg_obj.id}, ensure_ascii=False)}
        return
    if not candidates or all(c.get("score", 0) < settings.retrieval_threshold for c in candidates):
        # 诊断日志：输出候选数量及 top-3 分数
        if candidates:
            top3 = sorted([c.get("score", 0) for c in candidates], reverse=True)[:3]
            logger.warning(f"[{session_id}] 检索 {len(candidates)} 条候选均低于阈值 {settings.retrieval_threshold}，top3 分数: {top3}")
        else:
            logger.warning(f"[{session_id}] 检索无结果 — 请确认文档已入库且 Qdrant/Bm25 正常")
        # 检索无命中时也保存消息
        user_msg_obj = Message(session_id=session_id, role="user", content=user_message, intent=f"{intent_result['intent']}|{intent_result['source']}|{intent_result['confidence']}")
        ai_msg_obj = Message(session_id=session_id, role="assistant", content=FALLBACK_REPLY, references_json=[], token_count=len(FALLBACK_REPLY) // 2)
        db.add_all([user_msg_obj, ai_msg_obj])
        yield {"event": "delta", "data": json.dumps({'content': FALLBACK_REPLY}, ensure_ascii=False)}
        yield {"event": "done", "data": json.dumps({'message_id': ai_msg_obj.id}, ensure_ascii=False)}
        return

    # 按文档名去重，保留每个文档的最高分 + 第一条片段作为摘要
    seen_docs: dict[str, dict] = {}
    for c in candidates:
        doc_name = c.get("doc_name", "")
        if doc_name not in seen_docs:
            text = c.get("text", "")
            # 截取前 100 字作为片段摘要
            snippet = text[:100].replace("\n", " ").strip()
            seen_docs[doc_name] = {
                "doc_name": doc_name,
                "doc_id": c.get("doc_id", 0),
                "score": round(c.get("rrf", c.get("score", 0)), 3),
                "snippet": snippet,
            }
    references = list(seen_docs.values())[:5]
    yield {"event": "references", "data": json.dumps(references, ensure_ascii=False)}

    # 4. 重排序
    effective_k = get_effective_top_k(user_message)
    logger.info(f"[{session_id}] 有效 TOP_K={effective_k}（配置: floor={settings.retrieval_top_k_floor}, opt={settings.retrieval_top_k_opt}, default={settings.retrieval_top_k}）")
    try:
        top_docs = await rerank(retrieval_query, candidates[:10], top_n=effective_k)
    except Exception as e:
        logger.error(f"[{session_id}] 重排序异常，降级为未重排序结果: {e}")
        candidates.sort(key=lambda x: x.get("rrf", x.get("score", 0)), reverse=True)
        top_docs = candidates[:effective_k]
    logger.info(f"[{session_id}] 重排序 top-{len(top_docs)} 耗时 {time.time()-t_start:.2f}s")

    # 5. 上下文守护：分层摘要（使用精排分数）→ 类型排序（规则优先，最后一步确保不被覆盖）
    compressed = stratified_summarize(top_docs)
    compressed = prioritize_by_type(compressed)
    logger.info(f"[{session_id}] 候选数: {len(candidates)} -> 压缩排序后: {len(compressed)} 耗时 {time.time()-t_start:.2f}s")

    # 6. 构建提示词（过滤无文本内容的 chunk）
    history = await get_history(db, session_id, settings.max_context_rounds)
    valid_docs = [d for d in compressed if d.get("text", "").strip()]
    if not valid_docs:
        # 检索到文档但所有 chunk 都是空的（如扫描件 PDF）
        logger.warning(f"[{session_id}] 检索到 {len(compressed)} 条候选但均无有效文本")
        user_msg_obj = Message(session_id=session_id, role="user", content=user_message, intent=f"{intent_result['intent']}|{intent_result['source']}|{intent_result['confidence']}")
        ai_msg_obj = Message(session_id=session_id, role="assistant", content=FALLBACK_REPLY, references_json=references, token_count=len(FALLBACK_REPLY) // 2)
        db.add_all([user_msg_obj, ai_msg_obj])
        yield {"event": "delta", "data": json.dumps({'content': FALLBACK_REPLY}, ensure_ascii=False)}
        yield {"event": "done", "data": json.dumps({'message_id': ai_msg_obj.id}, ensure_ascii=False)}
        return
    knowledge_text = "\n\n---\n".join([
        f"【来源：{d.get('doc_name', '未知')}】{d.get('text', '')}"
        for d in valid_docs
    ])

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for h in history:
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": f"知识库内容：\n{knowledge_text}\n\n用户问题：{user_message}"})

    # 7. LLM 生成（SSE 流式输出）
    full_answer = ""
    try:
        async for token in chat_stream_with_fallback(messages):
            full_answer += token
            yield {"event": "delta", "data": json.dumps({'content': token}, ensure_ascii=False)}
    except Exception as e:
        logger.error(f"[{session_id}] LLM 生成失败: {e}")
        full_answer = FALLBACK_REPLY
        # 保存用户消息和兜底回复
        user_msg_obj = Message(session_id=session_id, role="user", content=user_message, intent=f"{intent_result['intent']}|{intent_result['source']}|{intent_result['confidence']}")
        ai_msg_obj = Message(session_id=session_id, role="assistant", content=full_answer, references_json=references, token_count=len(full_answer) // 2)
        db.add_all([user_msg_obj, ai_msg_obj])
        yield {"event": "delta", "data": json.dumps({'content': full_answer}, ensure_ascii=False)}
        yield {"event": "done", "data": json.dumps({'message_id': ai_msg_obj.id}, ensure_ascii=False)}
        return

    # 8. 步骤验证
    verification = verify_answer(full_answer, valid_docs)
    if not verification["pass"]:
        logger.warning(f"[{session_id}] 检测到未经验证的声明: {verification.get('unverified_claims')}")

    # 9. 保存消息
    user_msg_obj = Message(session_id=session_id, role="user", content=user_message, intent=f"{intent_result['intent']}|{intent_result['source']}|{intent_result['confidence']}")
    ai_msg_obj = Message(session_id=session_id, role="assistant", content=full_answer, references_json=references, token_count=len(full_answer) // 2)
    db.add_all([user_msg_obj, ai_msg_obj])

    # 如果是首条消息，更新会话标题
    result = await db.execute(select(Message).where(Message.session_id == session_id).limit(1))
    first_msg = result.scalar_one_or_none()
    if first_msg is None or first_msg.id == user_msg_obj.id:
        title = user_message[:30] + ("..." if len(user_message) > 30 else "")
        await db.execute(
            __import__("sqlalchemy").update(Session).where(Session.id == session_id).values(title=title)
        )

    # 10. 先发送 done，让前端立即结束 loading 状态
    yield {"event": "done", "data": json.dumps({'message_id': ai_msg_obj.id}, ensure_ascii=False)}

    # 10. 追问建议（异步生成，不阻塞主流程，最多 3 秒超时）
    followups = await generate_followups(user_message, full_answer, valid_docs)
    yield {"event": "followups", "data": json.dumps(followups, ensure_ascii=False)}

    logger.info(f"[{session_id}] RAG 完成 总耗时 {time.time()-t_start:.2f}s")


def _get_clarify_question(user_msg: str, intent_result: dict) -> str:
    """根据意图生成追问澄清问题"""
    intent = intent_result.get("intent", "")
    clarify_map = {
        "投诉": "您能具体描述一下遇到的问题吗？我会尽快帮您处理。",
        "售后问题": "请问您是想咨询退货、退款还是换货呢？",
        "产品咨询": "您是对哪款产品感兴趣呢？我可以为您详细介绍。",
        "订单查询": "请提供您的订单编号，我帮您查询。",
    }
    return clarify_map.get(intent, "抱歉，我没有完全理解您的意思，能再说得具体一些吗？")
