from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    kb_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("knowledge_bases.id"), default=None, nullable=True)
    title: Mapped[str] = mapped_column(String(200), default="新对话")
    status: Mapped[str] = mapped_column(Enum("active", "closed"), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
