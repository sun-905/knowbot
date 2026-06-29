"""集成测试 — 认证全流程（真实 MySQL）"""
import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_register_login_get_me():
    """注册 → 登录 → 获取用户信息"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        phone = f"138{str(uuid.uuid4().int)[-8:]}"

        # 1. 注册（不再返回 token）
        resp = await client.post("/auth/register", json={
            "phone": phone, "password": "test123456", "nickname": "int-test",
        })
        assert resp.status_code == 201, f"注册失败: {resp.text}"
        data = resp.json()
        assert "access_token" not in data
        assert data["user"]["phone"] == phone

        # 2. 登录获取 token
        resp_login = await client.post("/auth/login", json={
            "account": phone, "password": "test123456",
        })
        assert resp_login.status_code == 200
        token = resp_login.json()["access_token"]

        # 3. 获取用户信息
        resp2 = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp2.status_code == 200

        # 3. 错误 token → 401
        resp3 = await client.get("/auth/me", headers={"Authorization": "Bearer invalid"})
        assert resp3.status_code == 401

        # 4. 登录
        resp4 = await client.post("/auth/login", json={
            "account": phone, "password": "test123456",
        })
        assert resp4.status_code == 200

        # 5. 错误密码 → 401
        resp5 = await client.post("/auth/login", json={
            "account": phone, "password": "wrong",
        })
        assert resp5.status_code == 401


@pytest.mark.asyncio
async def test_register_duplicate_phone():
    """重复手机号注册返回 409"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        phone = f"137{str(uuid.uuid4().int)[-8:]}"
        resp1 = await client.post("/auth/register", json={
            "phone": phone, "password": "test123456", "nickname": "u1",
        })
        assert resp1.status_code == 201
        resp2 = await client.post("/auth/register", json={
            "phone": phone, "password": "test123456", "nickname": "u2",
        })
        assert resp2.status_code == 409
