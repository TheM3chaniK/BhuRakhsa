from typing import TypedDict
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.db.session import engine


class DatabaseHealthStatus(TypedDict):
    """Database health inspection result schema."""

    status: str
    postgresql: bool
    postgis: bool


class DatabaseHealthService:
    """Service to safely verify PostgreSQL connectivity and PostGIS extension status."""

    @staticmethod
    async def check_health(session: AsyncSession) -> DatabaseHealthStatus:
        """Verify PostgreSQL connection and PostGIS extension using an existing session."""
        pg_ok = False
        postgis_ok = False

        try:
            # 1. Verify PostgreSQL connection
            pg_result = await session.execute(text("SELECT 1;"))
            if pg_result.scalar() == 1:
                pg_ok = True

            # 2. Verify PostGIS extension
            postgis_result = await session.execute(text("SELECT PostGIS_Version();"))
            version_val = postgis_result.scalar()
            if version_val:
                postgis_ok = True
        except Exception as exc:
            logger.warning("Database health check error: %s", exc)

        is_healthy = pg_ok and postgis_ok
        return {
            "status": "ok" if is_healthy else "unhealthy",
            "postgresql": pg_ok,
            "postgis": postgis_ok,
        }

    @classmethod
    async def check_engine_health(cls) -> DatabaseHealthStatus:
        """Safely verify health by acquiring a connection directly from the engine."""
        try:
            async with engine.connect() as conn:
                pg_ok = False
                postgis_ok = False

                pg_result = await conn.execute(text("SELECT 1;"))
                if pg_result.scalar() == 1:
                    pg_ok = True

                try:
                    postgis_result = await conn.execute(text("SELECT PostGIS_Version();"))
                    version_val = postgis_result.scalar()
                    if version_val:
                        postgis_ok = True
                except Exception as exc:
                    logger.warning("PostGIS check failed during health verification: %s", exc)

                is_healthy = pg_ok and postgis_ok
                return {
                    "status": "ok" if is_healthy else "unhealthy",
                    "postgresql": pg_ok,
                    "postgis": postgis_ok,
                }
        except Exception as exc:
            logger.warning("Database engine connection failed during health verification: %s", exc)
            return {
                "status": "unhealthy",
                "postgresql": False,
                "postgis": False,
            }
