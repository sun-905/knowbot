from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..middleware.auth import get_current_user
from ..models.user import User
from ..services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["认证"])


# --- Request / Response Schemas ---

class RegisterRequest(BaseModel):
    phone: str
    email: str | None = None
    password: str
    nickname: str

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("密码长度不能少于6位")
        return v


class LoginRequest(BaseModel):
    account: str  # phone or email
    password: str


class UserResponse(BaseModel):
    id: int
    phone: str | None
    email: str | None
    nickname: str
    avatar_url: str
    daily_quota: int
    is_admin: bool
    created_at: str | None

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse


class RegisterResponse(BaseModel):
    message: str
    user: UserResponse


class UpdateUserRequest(BaseModel):
    nickname: str | None = None
    avatar_url: str | None = None


# --- Endpoints ---

@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    try:
        user = await auth_service.register(db, req.phone, req.email, req.password, req.nickname)
        return {
            "message": "注册成功，请登录",
            "user": auth_service._user_to_dict(user),
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    try:
        result = await auth_service.login(db, req.account, req.password)
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return auth_service._user_to_dict(current_user)


@router.patch("/me", response_model=UserResponse)
async def update_me(
    req: UpdateUserRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user = await auth_service.update_user(db, current_user, req.nickname, req.avatar_url)
    return auth_service._user_to_dict(user)
