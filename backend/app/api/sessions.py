from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..middleware.auth import get_current_user
from ..models.feedback import Feedback
from ..models.message import Message
from ..models.user import User

router = APIRouter(tags=["会话与反馈"])


class FeedbackRequest(BaseModel):
    rating: str  # "like" or "dislike"
    comment: str | None = None


class FeedbackResponse(BaseModel):
    id: int
    message_id: int
    rating: str
    comment: str | None

    model_config = {"from_attributes": True}


@router.post("/messages/{message_id}/feedback", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
async def submit_feedback(
    message_id: int,
    req: FeedbackRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if req.rating not in ("like", "dislike"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="评价类型必须为 like 或 dislike")

    # verify message exists
    msg_result = await db.execute(select(Message).where(Message.id == message_id))
    message = msg_result.scalar_one_or_none()
    if not message:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="消息不存在")

    # check duplicate
    existing = await db.execute(
        select(Feedback).where(
            Feedback.message_id == message_id,
            Feedback.user_id == current_user.id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="您已经评价过这条消息")

    feedback = Feedback(
        message_id=message_id,
        user_id=current_user.id,
        rating=req.rating,
        comment=req.comment,
    )
    db.add(feedback)
    await db.flush()
    await db.refresh(feedback)
    return feedback
