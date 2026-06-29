"""
查询改写服务

将用户的口语化、非正式表达改写为专业、精准的检索查询，
以提高向量检索和关键词检索的命中率。

核心策略：
1. 口语 → 专业术语（如"这玩意怎么退" → "退货流程"）
2. 模糊表达 → 精确表达（如"那个东西不好使" → "产品故障报修"）
3. 去除客套话、语气词、无关信息
4. 补全省略的主语和宾语
5. 保留原始语义，不做信息增删

集成方式：在意图识别之后、混合检索之前调用。
改写失败时自动降级为原始查询，不影响主流程。
"""

import asyncio
import json
import re

from loguru import logger

from ..core.config import settings
from ..core.llm_client import _get_deepseek

# 查询改写专用 system prompt
REWRITE_SYSTEM_PROMPT = """你是一个查询改写引擎。你的任务是将用户口语化的表达改写为专业、精准的检索查询。

改写规则：
1. 将口语词汇替换为专业术语（例："这玩意"→"该产品"、"不好使"→"故障/异常"、"怎么退"→"退货流程"）
2. 去除客套话、语气词（"请问一下"、"那个"、"嗯"、"啊"等）
3. 补全省略的主语、宾语，使查询语义完整
4. 保持原意，不要添加用户没提到的信息，也不要删除关键信息
5. 如果用户问题本身已经很专业清晰，就原样返回
6. 如果是闲聊（问候、感谢等），原样返回

输出格式：严格只返回改写后的一句话查询，不要任何解释、编号或多选。"""


async def rewrite_query(
    user_message: str,
    intent: str = "",
    timeout: float | None = None,
) -> str:
    """
    将用户消息改写为专业检索查询。

    参数：
        user_message: 用户原始消息
        intent: 意图分类结果（可选，用于判断是否需要改写）
        timeout: 超时秒数，默认使用配置值

    返回：
        改写后的查询字符串。改写失败或不需要改写时返回原始消息。
    """
    # 开关检查
    if not settings.query_rewrite_enabled:
        return user_message

    # 闲聊不需要改写
    if intent == "闲聊":
        return user_message

    # 消息太短（如纯标点、单字）不改写
    cleaned = user_message.strip()
    if len(cleaned) <= 2:
        return user_message

    # 消息过长（>500字）可能是粘贴的文档，不改写
    if len(cleaned) > 500:
        logger.info(f"查询过长({len(cleaned)}字)，跳过改写")
        return user_message

    if timeout is None:
        timeout = settings.query_rewrite_timeout

    try:
        client = _get_deepseek()
        rewritten = await asyncio.wait_for(
            _call_rewrite(client, user_message, intent),
            timeout=timeout,
        )
        # 有效性检查
        if rewritten and len(rewritten.strip()) >= 2:
            logger.info(f"查询改写: 「{user_message[:50]}」→「{rewritten[:80]}」")
            return rewritten.strip()
        else:
            logger.warning("改写结果过短，降级使用原始查询")
            return user_message

    except asyncio.TimeoutError:
        logger.warning(f"查询改写超时({timeout}s)，降级使用原始查询")
        return user_message
    except Exception as e:
        logger.error(f"查询改写失败: {e}，降级使用原始查询")
        return user_message


async def _call_rewrite(client, user_message: str, intent: str = "") -> str:
    """调用 LLM 执行改写"""
    user_prompt = f"意图：{intent}\n用户消息：{user_message}" if intent else user_message

    response = await client.chat.completions.create(
        model=settings.query_rewrite_model,
        messages=[
            {"role": "system", "content": REWRITE_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0,  # 确定性输出，保证改写一致性
        max_tokens=200,  # 改写后的查询不应超过原文太多
    )

    raw = response.choices[0].message.content.strip()

    # 清理 LLM 可能输出的多余格式
    # 去掉常见的编号前缀如 "1. "、"1) "、"改写："等
    raw = re.sub(r'^[\d]+[\.\)、]\s*', '', raw)
    raw = re.sub(r'^(改写|查询|检索)[：:]\s*', '', raw)
    # 去掉引号包裹
    raw = raw.strip('"\'')

    return raw


def rewrite_query_sync(user_message: str, intent: str = "") -> str:
    """
    同步版本，用于非异步上下文（如测试）。
    注意：这会创建新的事件循环，仅用于简单场景。
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # 在运行中的事件循环里，创建新任务
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run, rewrite_query(user_message, intent)
                )
                return future.result(timeout=settings.query_rewrite_timeout + 1)
        return asyncio.run(rewrite_query(user_message, intent))
    except RuntimeError:
        return asyncio.run(rewrite_query(user_message, intent))
