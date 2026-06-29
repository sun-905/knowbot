"""集成测试共享 fixtures — 真实 MySQL + Qdrant"""
import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest.fixture
def async_client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture
async def auth_token(async_client: AsyncClient):
    """注册测试用户并登录获取 token"""
    import uuid
    phone = f"139{str(uuid.uuid4().int)[-8:]}"

    # 先注册
    resp = await async_client.post("/auth/register", json={
        "phone": phone,
        "password": "test123456",
        "nickname": "集成测试用户",
    })
    if resp.status_code == 409:
        # 用户已存在，直接登录
        pass
    elif resp.status_code != 201:
        raise RuntimeError(f"注册失败: {resp.status_code} {resp.text}")

    # 再登录获取 token
    resp2 = await async_client.post("/auth/login", json={
        "account": phone,
        "password": "test123456",
    })
    if resp2.status_code == 200:
        return resp2.json()["access_token"]
    raise RuntimeError(f"无法获取token: register={resp.status_code}, login={resp2.status_code}")


@pytest.fixture
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}
