"""LLM 客户端容错机制单元测试"""
import pytest
from unittest.mock import patch, AsyncMock
import asyncio

from app.core.llm_client import (
    _circuit_breaker,
    _record_failure,
    _record_success,
    _failure_count,
    MAX_FAILURES,
    COOLDOWN_SECONDS,
    FALLBACK_MESSAGE,
    _circuit_open_until,
)


class TestCircuitBreaker:
    def setup_method(self):
        """每个测试前重置状态"""
        import app.core.llm_client as mod
        mod._failure_count = 0
        mod._circuit_open_until = None

    @pytest.mark.asyncio
    async def test_closed_by_default(self):
        assert _circuit_breaker() is False

    @pytest.mark.asyncio
    async def test_opens_after_max_failures(self):
        for _ in range(MAX_FAILURES):
            _record_failure()
        assert _circuit_breaker() is True

    @pytest.mark.asyncio
    async def test_not_open_before_max_failures(self):
        for _ in range(MAX_FAILURES - 1):
            _record_failure()
        assert _circuit_breaker() is False

    @pytest.mark.asyncio
    async def test_resets_after_cooldown(self):
        for _ in range(MAX_FAILURES):
            _record_failure()
        assert _circuit_breaker() is True

        import app.core.llm_client as mod
        mod._circuit_open_until = asyncio.get_event_loop().time() - 1
        assert _circuit_breaker() is False
        assert mod._failure_count == 0

    @pytest.mark.asyncio
    async def test_success_resets_failure_count(self):
        for _ in range(3):
            _record_failure()
        _record_success()
        import app.core.llm_client as mod
        assert mod._failure_count == 0


class TestFallbackMessage:
    def test_fallback_not_empty(self):
        assert len(FALLBACK_MESSAGE) > 0

    def test_fallback_is_chinese(self):
        assert "抱歉" in FALLBACK_MESSAGE or "无法" in FALLBACK_MESSAGE
