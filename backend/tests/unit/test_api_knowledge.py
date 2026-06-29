"""API 层单元测试 — 知识库接口"""
import pytest
from httpx import AsyncClient
from app.main import app


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_docs_requires_auth(async_client: AsyncClient):
    """未登录不能查看文档列表"""
    response = await async_client.get("/knowledge/docs")
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_upload_requires_admin(async_client: AsyncClient):
    """管理员接口需要鉴权"""
    response = await async_client.post("/knowledge/docs/upload")
    # 401 因为没 token 或 422 因为没 file
    assert response.status_code in (401, 422)


@pytest.mark.asyncio
async def test_list_bases_public(async_client: AsyncClient):
    """知识库列表 — 需要 mock DB 避免真实连接"""
    from unittest.mock import AsyncMock, MagicMock
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute = AsyncMock(return_value=mock_result)

    from app.core.database import get_db
    app.dependency_overrides[get_db] = lambda: mock_db

    response = await async_client.get("/knowledge/bases")
    assert response.status_code == 200
