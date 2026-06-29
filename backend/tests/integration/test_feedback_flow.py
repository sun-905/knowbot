"""集成测试 — 反馈全流程"""
import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_submit_feedback():
    """点赞一个消息"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 注册用户
        phone = f"135{str(uuid.uuid4().int)[-8:]}"
        resp = await client.post("/auth/register", json={
            "phone": phone, "password": "test123456", "nickname": "fb-test",
        })
        assert resp.status_code == 201
        resp2 = await client.post("/auth/login", json={"account": phone, "password": "test123456"})
        assert resp2.status_code == 200, f"登录失败: {resp2.text}"
        token = resp2.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 创建会话并发送消息
        resp = await client.post("/sessions", json={"title": "fb"}, headers=headers)
        session_id = resp.json()["id"]

        await client.post(
            f"/sessions/{session_id}/chat",
            json={"content": "你好"},
            headers=headers,
            timeout=60.0,
        )

        # 获取 assistant 消息 ID
        resp2 = await client.get(f"/sessions/{session_id}", headers=headers)
        messages = resp2.json().get("messages", [])
        assistant_msgs = [m for m in messages if m["role"] == "assistant"]
        if not assistant_msgs:
            pytest.skip("无 assistant 消息")
        msg_id = assistant_msgs[0]["id"]

        # 点赞
        resp3 = await client.post(
            f"/messages/{msg_id}/feedback",
            json={"rating": "like"},
            headers=headers,
        )
        assert resp3.status_code == 201

        # 重复反馈 → 409
        resp4 = await client.post(
            f"/messages/{msg_id}/feedback",
            json={"rating": "dislike", "comment": "不够好"},
            headers=headers,
        )
        assert resp4.status_code == 409
