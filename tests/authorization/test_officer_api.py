from unittest.mock import AsyncMock, patch
import pytest
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_current_user
from app.main import app
from app.models.area import Area
from app.models.user import User
from app.services.officer_service import OfficerService


@pytest.mark.anyio
async def test_officer_my_areas_endpoint(
    officer_a_user: User, civilian_user: User, area_a: Area
) -> None:
    """Verify GET /api/v1/officer/areas returns assigned areas for Area Officer."""
    with patch.object(
        OfficerService, "get_officer_areas", new_callable=AsyncMock
    ) as mock_areas:
        mock_areas.return_value = [area_a]

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            # 1. Area Officer -> 200 OK
            app.dependency_overrides[get_current_user] = lambda: officer_a_user
            res1 = await ac.get("/api/v1/officer/areas")
            assert res1.status_code == 200
            data = res1.json()
            assert len(data["areas"]) == 1
            assert data["areas"][0]["code"] == "AREA-NORTH"

            # 2. Civilian -> 403 Forbidden
            app.dependency_overrides[get_current_user] = lambda: civilian_user
            res2 = await ac.get("/api/v1/officer/areas")
            assert res2.status_code == 403
    app.dependency_overrides.clear()
