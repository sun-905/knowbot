import asyncio
from collections.abc import AsyncGenerator

import httpx
from loguru import logger
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .config import settings

_deepseek: AsyncOpenAI | None = None
_qwen: AsyncOpenAI | None = None
_failure_count = 0
_circuit_open_until: float | None = None
MAX_FAILURES = 5
COOLDOWN_SECONDS = 60
# LLM 请求超时：连接 5s，总计 45s（闲聊场景应远低于此值）
_LLM_TIMEOUT = httpx.Timeout(45.0, connect=5.0)


def _get_deepseek() -> AsyncOpenAI:
    global _deepseek
    if _deepseek is None:
        _deepseek = AsyncOpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            timeout=_LLM_TIMEOUT,
            max_retries=0,  # 由 tenacity 统一控制重试
        )
    return _deepseek


def _get_qwen() -> AsyncOpenAI:
    global _qwen
    if _qwen is None and settings.qwen_api_key:
        _qwen = AsyncOpenAI(
            api_key=settings.qwen_api_key,
            base_url=settings.qwen_base_url,
            timeout=_LLM_TIMEOUT,
            max_retries=0,
        )
    return _qwen


def _circuit_breaker() -> bool:
    """熔断器：连续失败后冷却一段时间"""
    global _circuit_open_until
    if _circuit_open_until and asyncio.get_event_loop().time() < _circuit_open_until:
        return True
    if _circuit_open_until and asyncio.get_event_loop().time() >= _circuit_open_until:
        _circuit_open_until = None
        global _failure_count
        _failure_count = 0
    return False


def _record_failure() -> None:
    """记录一次失败，达到阈值则打开熔断器"""
    global _failure_count, _circuit_open_until
    _failure_count += 1
    if _failure_count >= MAX_FAILURES:
        _circuit_open_until = asyncio.get_event_loop().time() + COOLDOWN_SECONDS
        logger.warning(f"LLM 熔断器已断开 — 冷却 {COOLDOWN_SECONDS}s")


def _record_success() -> None:
    """重置失败计数"""
    global _failure_count
    _failure_count = 0


FALLBACK_MESSAGE = "抱歉，我暂时无法处理您的请求，建议您稍后再试或联系人工客服。"


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    retry=retry_if_exception_type(Exception),
    reraise=False,
)
async def _try_client(client: AsyncOpenAI, model: str, messages: list[dict]) -> AsyncGenerator[str, None]:
    """尝试调用 LLM 客户端，支持流式输出"""
    response = await client.chat.completions.create(model=model, messages=messages, stream=True, temperature=0.7)
    async for chunk in response:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


async def chat_stream_with_fallback(messages: list[dict]) -> AsyncGenerator[str, None]:
    """带兜底的流式聊天：DeepSeek → Qwen → 静态兜底"""
    if _circuit_breaker():
        logger.warning("熔断器已断开 — 返回兜底消息")
        yield FALLBACK_MESSAGE
        return

    # 尝试 DeepSeek
    try:
        async for token in _try_client(_get_deepseek(), settings.llm_model, messages):
            yield token
        _record_success()
        return
    except Exception as e:
        logger.error(f"DeepSeek 调用失败: {e}")
        _record_failure()

    # 尝试 Qwen 兜底
    qwen = _get_qwen()
    if qwen:
        try:
            async for token in _try_client(qwen, "qwen-turbo", messages):
                yield token
            _record_success()
            return
        except Exception as e:
            logger.error(f"Qwen 兜底也失败: {e}")
            _record_failure()

    # 静态兜底
    yield FALLBACK_MESSAGE
