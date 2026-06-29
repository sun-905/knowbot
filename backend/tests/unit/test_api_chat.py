"""API 层单元测试 — 对话接口"""
import pytest
from httpx import AsyncClient
from app.models.user import User
from app.main import app


@pytest.fixture(autouse=True)
def clear_overrides():
    """每个测试后清理 dependency overrides"""
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_session_requires_auth(async_client: AsyncClient):
    """未登录不能创建会话"""
    response = await async_client.post("/sessions", json={"title": "test"})
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_list_sessions_requires_auth(async_client: AsyncClient):
    """未登录不能列会话"""
    response = await async_client.get("/sessions")
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_chat_with_auth(async_client: AsyncClient):
    """已登录用户访问聊天接口"""
    from app.middleware.auth import get_current_user
    mock_user = User(id=1, phone="13800138000", nickname="test", is_admin=False)
    app.dependency_overrides[get_current_user] = lambda: mock_user

    response = await async_client.post("/sessions/99999/chat", json={"content": "hello"})
    # SSE 连接可能返回 200
    assert response.status_code in (200, 404)
