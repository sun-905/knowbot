"""集成测试 — 对话全流程（真实 MySQL + Qdrant + DeepSeek）"""
import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from app.main import app


async def _register_and_get_token(client: AsyncClient) -> str:
    phone = f"136{str(uuid.uuid4().int)[-8:]}"
    # 注册
    resp = await client.post("/auth/register", json={
        "phone": phone, "password": "test123456", "nickname": "chat-test",
    })
    assert resp.status_code == 201, resp.text
    # 登录获取 token
    resp2 = await client.post("/auth/login", json={
        "account": phone, "password": "test123456",
    })
    assert resp2.status_code == 200, resp2.text
    return resp2.json()["access_token"]


@pytest.mark.asyncio
async def test_create_and_list_sessions():
    """创建会话 → 列出会话"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _register_and_get_token(client)
        headers = {"Authorization": f"Bearer {token}"}

        resp = await client.post("/sessions", json={"title": "test"}, headers=headers)
        assert resp.status_code in (200, 201)
        assert "id" in resp.json()

        resp2 = await client.get("/sessions", headers=headers)
        assert resp2.status_code == 200
        assert resp2.json()["total"] >= 1


@pytest.mark.asyncio
async def test_chat_sse_events():
    """发送消息 → 验证 SSE 事件有 intent + done"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _register_and_get_token(client)
        headers = {"Authorization": f"Bearer {token}"}

        resp = await client.post("/sessions", json={"title": "sse test"}, headers=headers)
        session_id = resp.json()["id"]

        resp2 = await client.post(
            f"/sessions/{session_id}/chat",
            json={"content": "你好"},
            headers=headers,
            timeout=60.0,
        )
        assert resp2.status_code == 200
        body = resp2.text

        # 检查关键 SSE 事件
        assert "event: intent" in body, f"缺少 intent 事件\nBody: {body[:300]}"
        assert "event: done" in body, f"缺少 done 事件\nBody: {body[:300]}"


@pytest.mark.asyncio
async def test_chat_persists_messages():
    """发消息后消息持久化"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _register_and_get_token(client)
        headers = {"Authorization": f"Bearer {token}"}

        resp = await client.post("/sessions", json={"title": "persist"}, headers=headers)
        session_id = resp.json()["id"]

        await client.post(
            f"/sessions/{session_id}/chat",
            json={"content": "你好"},
            headers=headers,
            timeout=60.0,
        )

        resp2 = await client.get(f"/sessions/{session_id}", headers=headers)
        messages = resp2.json().get("messages", [])
        assert len(messages) >= 2, f"应有至少2条消息，实际{len(messages)}条"
