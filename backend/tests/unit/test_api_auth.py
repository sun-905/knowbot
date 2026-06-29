"""API 层单元测试 — 认证接口"""
import pytest
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_success(async_client: AsyncClient):
    """正常注册返回 201 + message + user（不返回 token，需另行登录）"""
    mock_user = AsyncMock()
    mock_user.id = 1
    mock_user.phone = "13800138000"
    mock_user.email = None
    mock_user.nickname = "测试"
    mock_user.avatar_url = ""
    mock_user.daily_quota = 100
    mock_user.is_admin = False
    mock_user.created_at = None

    with patch("app.api.auth.auth_service.register", AsyncMock(return_value=mock_user)):
        with patch("app.api.auth.get_db", AsyncMock()):
            response = await async_client.post("/auth/register", json={
                "phone": "13800138000",
                "password": "test123456",
                "nickname": "测试",
            })
            assert response.status_code == 201
            data = response.json()
            assert "access_token" not in data
            assert data["message"] == "注册成功，请登录"
            assert data["user"]["nickname"] == "测试"


@pytest.mark.asyncio
async def test_register_missing_phone(async_client: AsyncClient):
    """手机号必填，缺少时 422"""
    response = await async_client.post("/auth/register", json={
        "password": "test123456",
        "nickname": "测试",
    })
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_short_password(async_client: AsyncClient):
    """密码少于6位时 422"""
    response = await async_client.post("/auth/register", json={
        "phone": "13800138000",
        "password": "12345",
        "nickname": "测试",
    })
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_success(async_client: AsyncClient):
    """登录成功返回 token"""
    mock_result = {
        "access_token": "fake-token",
        "token_type": "bearer",
        "user": {
            "id": 1, "phone": "13800138000", "email": None,
            "nickname": "测试", "avatar_url": "", "daily_quota": 100,
            "is_admin": False, "created_at": None,
        },
    }

    with patch("app.api.auth.auth_service.login", AsyncMock(return_value=mock_result)):
        with patch("app.api.auth.get_db", AsyncMock()):
            response = await async_client.post("/auth/login", json={
                "account": "13800138000",
                "password": "test123456",
            })
            assert response.status_code == 200
            assert response.json()["access_token"] == "fake-token"


@pytest.mark.asyncio
async def test_login_invalid(async_client: AsyncClient):
    """登录失败返回 401"""
    with patch("app.api.auth.auth_service.login", AsyncMock(side_effect=ValueError("账号或密码错误"))):
        with patch("app.api.auth.get_db", AsyncMock()):
            response = await async_client.post("/auth/login", json={
                "account": "13800138000",
                "password": "wrong",
            })
            assert response.status_code == 401


@pytest.mark.asyncio
async def test_health_check(async_client: AsyncClient):
    """健康检查"""
    response = await async_client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
