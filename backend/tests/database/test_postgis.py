import pytest
from sqlalchemy import text

from app.db.session import engine
from tests.database.conftest import check_db_connectivity


@pytest.mark.anyio
async def test_postgis_version_query() -> None:
    """Verify that PostGIS extension is installed and PostGIS_Version() returns a valid string."""
    if not await check_db_connectivity():
        pytest.skip("PostgreSQL is not running at DATABASE_URL")

    async with engine.connect() as conn:
        try:
            result = await conn.execute(text("SELECT PostGIS_Version();"))
            version_str = result.scalar()
            assert version_str is not None
            assert isinstance(version_str, str)
            assert len(version_str) > 0
        except Exception as exc:
            pytest.fail(f"PostGIS extension query failed: {exc}")


@pytest.mark.anyio
async def test_postgis_geometry_type_available() -> None:
    """Verify that PostGIS geometry data types and core spatial functions are accessible."""
    if not await check_db_connectivity():
        pytest.skip("PostgreSQL is not running at DATABASE_URL")

    async with engine.connect() as conn:
        # Check basic point construction in SRID 4326 (WGS84)
        result = await conn.execute(
            text("SELECT ST_AsText(ST_SetSRID(ST_Point(77.2090, 28.6139), 4326));")
        )
        point_wkt = result.scalar()
        assert point_wkt == "POINT(77.209 28.6139)"
