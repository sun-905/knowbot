"""单题快速验证"""
import sys, io, json, asyncio, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

async def main():
    from httpx import AsyncClient, ASGITransport
    from app.main import app
    from tests.rag_eval.judge import check_hard_assertions

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        # 注册
        import uuid
        phone = f"130{str(uuid.uuid4().int)[-8:]}"
        r = await c.post("/auth/register", json={"phone": phone, "password": "test123", "nickname": "eval"})
        r2 = await c.post("/auth/login", json={"account": phone, "password": "test123"})
        token = r2.json()["access_token"]
        h = {"Authorization": f"Bearer {token}"}

        # 创建会话
        r2 = await c.post("/sessions", json={"title": "test"}, headers=h)
        sid = r2.json()["id"]
        print(f"Session: {sid}")

        # 发送问题
        print("Sending question: X1 多少钱？")
        r3 = await c.post(f"/sessions/{sid}/chat", json={"content": "智能门锁 X1 多少钱？"}, headers=h, timeout=120.0)

        answer = ""
        for line in r3.text.split("\n"):
            if line.startswith("data: "):
                try:
                    obj = json.loads(line[6:])
                    if "content" in obj:
                        answer += obj["content"]
                except: pass

        print(f"Answer: {answer[:200]}")
        hard = check_hard_assertions("A1", answer)
        print(f"Hard assertions: {hard}")

asyncio.run(main())
" 2>&1