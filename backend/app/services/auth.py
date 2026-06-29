from datetime import datetime, timedelta

from jose import jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..models.user import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(user_id: int) -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


async def register(db: AsyncSession, phone: str | None, email: str | None, password: str, nickname: str = "") -> User:
    if phone:
        result = await db.execute(select(User).where(User.phone == phone))
        if result.scalar_one_or_none():
            raise ValueError("手机号已被注册")
    if email:
        result = await db.execute(select(User).where(User.email == email))
        if result.scalar_one_or_none():
            raise ValueError("邮箱已被注册")

    user = User(
        phone=phone,
        email=email,
        password_hash=hash_password(password),
        nickname=nickname or "",
        daily_quota=settings.daily_quota_limit,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


async def login(db: AsyncSession, account: str, password: str) -> dict:
    result = await db.execute(
        select(User).where((User.phone == account) | (User.email == account)).limit(1)
    )
    user = result.scalar_one_or_none()
    if not user or not verify_password(password, user.password_hash):
        raise ValueError("账号或密码错误")
    if not user.is_active:
        raise ValueError("账号已被禁用")

    token = create_access_token(user.id)
    return {"access_token": token, "token_type": "bearer", "user": _user_to_dict(user)}


async def get_user(db: AsyncSession, user_id: int) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def update_user(db: AsyncSession, user: User, nickname: str | None, avatar_url: str | None) -> User:
    if nickname is not None:
        user.nickname = nickname
    if avatar_url is not None:
        user.avatar_url = avatar_url
    await db.flush()
    await db.refresh(user)
    return user


def _user_to_dict(user: User) -> dict:
    return {
        "id": user.id,
        "phone": user.phone,
        "email": user.email,
        "nickname": user.nickname,
        "avatar_url": user.avatar_url,
        "daily_quota": user.daily_quota,
        "is_admin": user.is_admin,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }
