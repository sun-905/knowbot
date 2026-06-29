"""共享 fixtures：HTTP 客户端、测试数据库、测试用户"""
import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest.fixture
def async_client():
    """创建异步 HTTP 测试客户端"""
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture
def test_phone():
    return "13800138000"


@pytest.fixture
def test_email():
    return "test@example.com"


@pytest.fixture
def test_password():
    return "test123456"
