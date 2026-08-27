from unittest.mock import AsyncMock, patch
import pytest
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_current_user
from app.main import app
from app.models.user import User
from app.schemas.admin import (
    AdminSummaryResponse,
    AreaStats,
    OfficerStats,
    UserStats,
)
from app.services.area_service import AreaService


@pytest.mark.anyio
async def test_admin_summary_endpoint(
    super_admin_user: User, officer_a_user: User, civilian_user: User
) -> None:
    """Verify GET /api/v1/admin/summary metrics and RBAC."""
    mock_summary = AdminSummaryResponse(
        users=UserStats(
            total=10,
            civilians=7,
            area_officers=2,
            super_admins=1,
            active=9,
            inactive=1,
        ),
        areas=AreaStats(
            total=4,
            active=3,
            inactive=1,
        ),
        officers=OfficerStats(
            assigned=2,
            unassigned=0,
        ),
    )

    with patch.object(
        AreaService, "get_admin_summary", new_callable=AsyncMock
    ) as mock_sum:
        mock_sum.return_value = mock_summary

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            # 1. Super Admin -> 200 OK
            app.dependency_overrides[get_current_user] = lambda: super_admin_user
            res1 = await ac.get("/api/v1/admin/summary")
            assert res1.status_code == 200
            data = res1.json()
            assert data["users"]["total"] == 10
            assert data["users"]["civilians"] == 7
            assert data["areas"]["active"] == 3
            assert data["officers"]["assigned"] == 2

            # 2. Area Officer -> 403 Forbidden
            app.dependency_overrides[get_current_user] = lambda: officer_a_user
            res2 = await ac.get("/api/v1/admin/summary")
            assert res2.status_code == 403

            # 3. Civilian -> 403 Forbidden
            app.dependency_overrides[get_current_user] = lambda: civilian_user
            res3 = await ac.get("/api/v1/admin/summary")
            assert res3.status_code == 403
    app.dependency_overrides.clear()
