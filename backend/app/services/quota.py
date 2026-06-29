from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..models.daily_usage import DailyUsage

# 用户并发 SSE 连接数追踪
_concurrent: dict[int, int] = {}
MAX_CONCURRENT = 5  # SSE 重连可能瞬时超过 3，留出余量


async def check_daily_quota(db: AsyncSession, user_id: int) -> None:
    """检查并扣减每日提问配额"""
    today = date.today()

    result = await db.execute(
        select(DailyUsage).where(
            DailyUsage.user_id == user_id,
            DailyUsage.usage_date == today,
        ).with_for_update()
    )
    usage = result.scalar_one_or_none()

    if usage is None:
        usage = DailyUsage(user_id=user_id, usage_date=today, count=0)
        db.add(usage)
        await db.flush()

    if usage.count >= settings.daily_quota_limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="今日提问次数已用完，请明天再试",
        )

    usage.count += 1
    await db.flush()


async def check_concurrent_limit(user_id: int) -> None:
    """检查并发连接数限制"""
    current = _concurrent.get(user_id, 0)
    if current >= MAX_CONCURRENT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="当前连接数过多，请稍后再试",
        )
    _concurrent[user_id] = current + 1


async def release_concurrent(user_id: int) -> None:
    """释放一个并发连接"""
    current = _concurrent.get(user_id, 0)
    if current > 0:
        _concurrent[user_id] = current - 1
