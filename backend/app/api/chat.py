import asyncio
import json
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..middleware.auth import get_current_user
from ..models.session import Session
from ..models.user import User
from ..services.chat import rag_chat_stream
from ..services.quota import check_concurrent_limit, check_daily_quota, release_concurrent

CST = timezone(timedelta(hours=8))


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=CST)
    return dt.isoformat()


def _format_sse(event: dict) -> str:
    """将 {event, data} 字典格式化为 SSE 字符串"""
    lines = []
    for key in ("event", "data", "id", "retry"):
        if key in event:
            lines.append(f"{key}: {event[key]}")
    return "\n".join(lines) + "\n\n"


def _sse_wrapper(generator):
    """包装异步生成器：格式化 SSE + 后台 keepalive ping + 正确清理"""
    async def inner():
        queue: asyncio.Queue[tuple[str, dict | None]] = asyncio.Queue()
        done = False

        async def pump_events():
            """从原始生成器读取事件并放入队列"""
            nonlocal done
            try:
                async for event in generator:
                    await queue.put(("event", event))
            except Exception:
                pass
            finally:
                done = True
                await queue.put(("done", None))

        async def send_pings():
            """每 3 秒放一个 ping 到队列"""
            try:
                while not done:
                    await asyncio.sleep(3)
                    if not done:
                        await queue.put(("ping", None))
            except asyncio.CancelledError:
                pass

        event_task = asyncio.create_task(pump_events())
        ping_task = asyncio.create_task(send_pings())

        try:
            while True:
                msg_type, payload = await queue.get()
                if msg_type == "done":
                    break
                if msg_type == "ping":
                    yield ": ping\n\n"
                else:
                    yield _format_sse(payload)
        finally:
            done = True
            event_task.cancel()
            ping_task.cancel()
            await asyncio.gather(event_task, ping_task, return_exceptions=True)

    return inner()


router = APIRouter(tags=["对话"])


class ChatRequest(BaseModel):
    content: str

    @field_validator("content")
    @classmethod
    def content_length(cls, v: str) -> str:
        if len(v) < 1:
            raise ValueError("消息内容不能为空")
        if len(v) > 500:
            raise ValueError("消息内容不能超过500字")
        return v


class SessionCreate(BaseModel):
    title: str = "新对话"
    kb_id: int | None = None  # 可选，指定知识库；不传则查全部


@router.post("/sessions", status_code=status.HTTP_201_CREATED)
async def create_session(
    req: SessionCreate = SessionCreate(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = Session(user_id=current_user.id, title=req.title, kb_id=req.kb_id)
    db.add(session)
    await db.flush()
    await db.refresh(session)
    await db.commit()
    return {
        "id": session.id, "title": session.title, "user_id": session.user_id,
        "status": session.status, "kb_id": session.kb_id,
    }


@router.get("/sessions")
async def list_sessions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    offset = (page - 1) * page_size
    result = await db.execute(
        select(Session)
        .where(Session.user_id == current_user.id)
        .order_by(Session.updated_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    sessions = result.scalars().all()
    total_result = await db.execute(
        __import__("sqlalchemy").select(__import__("sqlalchemy").func.count(Session.id))
        .where(Session.user_id == current_user.id)
    )
    total = total_result.scalar()
    return {
        "items": [{"id": s.id, "title": s.title, "status": s.status, "kb_id": s.kb_id, "created_at": _iso(s.created_at)} for s in sessions],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")
    if session.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问此会话")

    from ..models.message import Message
    msg_result = await db.execute(
        select(Message).where(Message.session_id == session_id).order_by(Message.created_at.asc())
    )
    messages = msg_result.scalars().all()

    return {
        "id": session.id,
        "title": session.title,
        "status": session.status,
        "kb_id": session.kb_id,
        "messages": [
            {"id": m.id, "role": m.role, "content": m.content, "intent": m.intent, "references_json": m.references_json, "created_at": _iso(m.created_at)}
            for m in messages
        ],
    }


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")
    if session.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权删除此会话")
    await db.delete(session)
    await db.flush()


@router.post("/sessions/{session_id}/chat")
async def chat(
    session_id: int,
    req: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # 配额检查（请求开始前快速失败，使用请求级 db session）
    await check_daily_quota(db, current_user.id)
    await check_concurrent_limit(current_user.id)

    async def event_generator():
        # SSE 流独立 session — 不依赖 FastAPI Depends 的生命周期，避免连接泄漏
        from ..core.database import async_session
        sse_db = async_session()
        stream_error = False
        try:
            result = await sse_db.execute(select(Session).where(Session.id == session_id))
            session = result.scalar_one_or_none()
            if not session:
                yield {"event": "error", "data": json.dumps({"code": "session_not_found", "detail": "会话不存在，请创建新对话"}, ensure_ascii=False)}
                return
            if session.user_id != current_user.id:
                yield {"event": "error", "data": json.dumps({"code": "forbidden", "detail": "无权在此会话中发送消息"}, ensure_ascii=False)}
                return

            async for event in rag_chat_stream(sse_db, session_id, current_user.id, req.content, kb_id=session.kb_id):
                yield event
        except (asyncio.CancelledError, ConnectionError):
            stream_error = True
        except Exception as e:
            stream_error = True
            from loguru import logger
            logger.error(f"SSE 流异常: {e}")
            try:
                yield {"event": "error", "data": json.dumps({"code": "internal", "detail": "服务器处理请求时出错，请重试"}, ensure_ascii=False)}
            except Exception:
                pass
        finally:
            # shield 保护清理操作不被取消，确保连接正确归还池
            async def _cleanup():
                if stream_error:
                    try:
                        await sse_db.rollback()
                    except Exception:
                        pass
                else:
                    try:
                        await sse_db.commit()
                    except Exception:
                        pass
                try:
                    await sse_db.close()
                except Exception:
                    pass
                try:
                    await release_concurrent(current_user.id)
                except Exception:
                    pass
            try:
                await asyncio.shield(_cleanup())
            except asyncio.CancelledError:
                pass

    return StreamingResponse(
        _sse_wrapper(event_generator()),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )
