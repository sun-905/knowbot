"""认证服务单元测试"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.auth import (
    hash_password,
    verify_password,
    create_access_token,
    register,
    login,
    _user_to_dict,
)
from app.models.user import User


class TestPasswordHashing:
    def test_hash_different_each_time(self):
        h1 = hash_password("mypassword")
        h2 = hash_password("mypassword")
        assert h1 != h2  # bcrypt salt 不同

    def test_verify_correct_password(self):
        hashed = hash_password("mypassword")
        assert verify_password("mypassword", hashed) is True

    def test_verify_wrong_password(self):
        hashed = hash_password("mypassword")
        assert verify_password("wrong", hashed) is False


class TestJWT:
    def test_create_and_decode(self):
        from jose import jwt
        from app.core.config import settings

        token = create_access_token(42)
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        assert payload["sub"] == "42"
        assert "exp" in payload


class TestRegister:
    @pytest.mark.asyncio
    async def test_register_success(self):
        db = AsyncMock()
        # phone 查询 → None, email 查询 → None
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute.return_value = mock_result
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()

        user = await register(db, "13800138000", "test@test.com", "pass123", "测试")
        assert user.phone == "13800138000"
        assert user.email == "test@test.com"
        assert user.nickname == "测试"

    @pytest.mark.asyncio
    async def test_register_duplicate_phone(self):
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = User(phone="13800138000")
        db.execute.return_value = mock_result

        with pytest.raises(ValueError, match="手机号已被注册"):
            await register(db, "13800138000", None, "pass123", "测试")

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self):
        db = AsyncMock()
        # phone=None 跳过 phone 检查, email 查询返回已存在
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = User(email="dup@test.com")
        db.execute.return_value = mock_result

        with pytest.raises(ValueError, match="邮箱已被注册"):
            await register(db, None, "dup@test.com", "pass123", "test")


class TestLogin:
    @pytest.mark.asyncio
    async def test_login_by_phone(self):
        db = AsyncMock()
        user = User(id=1, phone="13800138000", nickname="测试用户", is_active=True)
        user.password_hash = hash_password("correct")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = user
        db.execute.return_value = mock_result

        result = await login(db, "13800138000", "correct")
        assert "access_token" in result
        assert result["user"]["id"] == 1

    @pytest.mark.asyncio
    async def test_login_wrong_password(self):
        db = AsyncMock()
        user = User(id=1, is_active=True)
        user.password_hash = hash_password("correct")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = user
        db.execute.return_value = mock_result

        with pytest.raises(ValueError, match="账号或密码错误"):
            await login(db, "13800138000", "wrong")

    @pytest.mark.asyncio
    async def test_login_disabled_user(self):
        db = AsyncMock()
        user = User(id=1, is_active=False)
        user.password_hash = hash_password("correct")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = user
        db.execute.return_value = mock_result

        with pytest.raises(ValueError, match="账号已被禁用"):
            await login(db, "13800138000", "correct")

    @pytest.mark.asyncio
    async def test_login_user_not_found(self):
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute.return_value = mock_result

        with pytest.raises(ValueError, match="账号或密码错误"):
            await login(db, "13800138000", "any")


class TestUserToDict:
    def test_full_user(self):
        user = User(id=1, phone="138", email="a@b.com", nickname="小明", is_admin=True)
        d = _user_to_dict(user)
        assert d["id"] == 1
        assert d["phone"] == "138"
        assert d["is_admin"] is True
