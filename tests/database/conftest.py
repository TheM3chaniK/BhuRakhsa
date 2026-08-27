import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_factory, engine


async def check_db_connectivity() -> bool:
    """Helper to verify if PostgreSQL is reachable."""
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1;"))
            return result.scalar() == 1
    except Exception:
        return False


def check_db_connectivity_sync() -> bool:
    """Helper to synchronously verify if PostgreSQL is reachable."""
    try:
        from sqlalchemy import create_engine, pool
        from app.core.config import settings

        sync_engine = create_engine(
            settings.DATABASE_URL,
            connect_args={"connect_timeout": 3},
            poolclass=pool.NullPool,
        )
        with sync_engine.connect() as conn:
            result = conn.execute(text("SELECT 1;"))
            return result.scalar() == 1
    except Exception:
        return False


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def db_session() -> AsyncSession:
    """Yield a database session for test cases."""
    async with async_session_factory() as session:
        yield session
