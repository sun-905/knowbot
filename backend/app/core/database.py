from pymysql.err import InterfaceError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .config import settings

engine = create_async_engine(settings.database_url, pool_size=10, max_overflow=20, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    """获取数据库会话的依赖注入生成器

    客户端断开时 MySQL 连接会被取消，commit 会抛 InterfaceError，
    这种场景下静默回滚即可，不需要报错。
    """
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except InterfaceError:
            # 客户端断开导致连接取消，静默回滚
            await session.rollback()
        except Exception:
            await session.rollback()
            raise
