import pytest
from sqlalchemy import text

from app.db.session import engine, get_db
from app.services.database_health_service import DatabaseHealthService
from tests.database.conftest import check_db_connectivity


@pytest.mark.anyio
async def test_get_db_dependency_lifecycle() -> None:
    """Verify that get_db yields an async session and closes cleanly."""
    gen = get_db()
    session = await anext(gen)
    assert session is not None
    assert hasattr(session, "execute")
    assert hasattr(session, "close")

    # Clean close
    with pytest.raises(StopAsyncIteration):
        await anext(gen)


@pytest.mark.anyio
async def test_postgresql_connection_and_select_1() -> None:
    """Verify PostgreSQL connectivity and execution of SELECT 1."""
    if not await check_db_connectivity():
        pytest.skip("PostgreSQL is not running at DATABASE_URL")

    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT 1;"))
        assert result.scalar() == 1


@pytest.mark.anyio
async def test_database_health_service_live() -> None:
    """Verify DatabaseHealthService response on a live database connection."""
    if not await check_db_connectivity():
        pytest.skip("PostgreSQL is not running at DATABASE_URL")

    health_status = await DatabaseHealthService.check_engine_health()
    assert health_status["postgresql"] is True
    assert isinstance(health_status["postgis"], bool)
    assert health_status["status"] in ("ok", "unhealthy")
