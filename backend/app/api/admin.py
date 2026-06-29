from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..middleware.auth import require_admin
from ..models.daily_usage import DailyUsage
from ..models.feedback import Feedback
from ..models.message import Message
from ..models.session import Session
from ..models.user import User

router = APIRouter(prefix="/admin", tags=["管理后台"])


class StatsResponse(BaseModel):
    metric: str
    value: int | float


@router.get("/sessions")
async def list_all_sessions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    offset = (page - 1) * page_size
    result = await db.execute(
        select(Session).order_by(Session.created_at.desc()).offset(offset).limit(page_size)
    )
    sessions = result.scalars().all()
    total_result = await db.execute(select(func.count(Session.id)))
    total = total_result.scalar()
    return {
        "items": [
            {
                "id": s.id,
                "user_id": s.user_id,
                "title": s.title,
                "status": s.status,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "updated_at": s.updated_at.isoformat() if s.updated_at else None,
            }
            for s in sessions
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/stats/daily")
async def daily_stats(
    days: int = Query(default=7, ge=1, le=90),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    since = date.today() - timedelta(days=days - 1)
    result = await db.execute(
        select(DailyUsage.usage_date, func.sum(DailyUsage.count).label("total"))
        .where(DailyUsage.usage_date >= since)
        .group_by(DailyUsage.usage_date)
        .order_by(DailyUsage.usage_date.asc())
    )
    rows = result.all()
    return {
        "days": days,
        "data": [
            {"date": str(row.usage_date), "total_questions": int(row.total)}
            for row in rows
        ],
        "summary": {
            "total_questions": sum(int(row.total) for row in rows),
            "avg_daily": round(sum(int(row.total) for row in rows) / max(len(rows), 1), 1),
        },
    }


@router.get("/stats/feedback")
async def feedback_stats(
    days: int = Query(default=7, ge=1, le=90),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    since = date.today() - timedelta(days=days - 1)
    result = await db.execute(
        select(
            func.date(Feedback.created_at).label("dt"),
            func.sum(text("case when rating='like' then 1 else 0 end")).label("likes"),
            func.sum(text("case when rating='dislike' then 1 else 0 end")).label("dislikes"),
            func.count(Feedback.id).label("total"),
        )
        .where(Feedback.created_at >= since)
        .group_by(text("dt"))
        .order_by(text("dt"))
    )
    rows = result.all()
    total_likes = sum(r.likes for r in rows)
    total_dislikes = sum(r.dislikes for r in rows)
    total_all = total_likes + total_dislikes

    return {
        "days": days,
        "data": [
            {
                "date": str(row.dt),
                "likes": int(row.likes),
                "dislikes": int(row.dislikes),
                "total": int(row.total),
            }
            for row in rows
        ],
        "summary": {
            "total_likes": total_likes,
            "total_dislikes": total_dislikes,
            "total_feedbacks": total_all,
            "like_rate": round(total_likes / max(total_all, 1) * 100, 1),
        },
    }


@router.get("/stats/intent")
async def intent_stats(
    days: int = Query(default=7, ge=1, le=90),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    since = date.today() - timedelta(days=days - 1)
    result = await db.execute(
        select(Message.intent, func.count(Message.id).label("cnt"))
        .where(Message.created_at >= since, Message.intent.isnot(None))
        .group_by(Message.intent)
        .order_by(text("cnt DESC"))
    )
    rows = result.all()
    total = sum(row.cnt for row in rows)

    return {
        "days": days,
        "data": [
            {
                "intent": row.intent.split("|")[0] if row.intent and "|" in row.intent else (row.intent or "未知"),
                "count": row.cnt,
                "pct": round(row.cnt / max(total, 1) * 100, 1),
            }
            for row in rows
        ],
        "summary": {"total_classified": total},
    }


@router.get("/feedback-comments")
async def feedback_comments(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """分页查询带文字反馈的记录（comment 非空即为差评）"""
    offset = (page - 1) * page_size
    result = await db.execute(
        select(Feedback, User.nickname, User.phone, User.email)
        .join(User, Feedback.user_id == User.id)
        .where(Feedback.comment.isnot(None), Feedback.comment != "")
        .order_by(Feedback.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    rows = result.all()

    total_result = await db.execute(
        select(func.count(Feedback.id)).where(
            Feedback.comment.isnot(None), Feedback.comment != ""
        )
    )
    total = total_result.scalar()

    return {
        "items": [
            {
                "id": row.Feedback.id,
                "rating": row.Feedback.rating,
                "comment": row.Feedback.comment,
                "message_id": row.Feedback.message_id,
                "user": {
                    "nickname": row.nickname,
                    "phone": row.phone,
                    "email": row.email,
                },
                "created_at": row.Feedback.created_at.isoformat() if row.Feedback.created_at else None,
            }
            for row in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }
