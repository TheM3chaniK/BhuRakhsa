from unittest.mock import AsyncMock, patch
from httpx import ASGITransport, AsyncClient
import pytest

from app.api.dependencies import get_current_user
from app.main import app
from app.models.user import User
from app.schemas.admin_dashboard import (
    AdminDashboardResponse,
    AreaSummaryCounts,
    CaseSummaryCounts,
    ProcessingSummaryCounts,
    RiskSummaryCounts,
    UserSummaryCounts,
)
from app.services.admin_dashboard_service import AdminDashboardService


@pytest.mark.anyio
async def test_admin_dashboard_metrics(super_admin_user: User, civilian_user: User, officer_a_user: User) -> None:
    """Verify Super Admin can retrieve aggregated dashboard metrics, while non-admins are rejected."""
    mock_dashboard = AdminDashboardResponse(
        areas=AreaSummaryCounts(total=10, active=10),
        users=UserSummaryCounts(civilians=1500, area_officers=25),
        cases=CaseSummaryCounts(total=1200, under_review=35, proof_required=12, approved=950, rejected=203),
        risk=RiskSummaryCounts(critical=5, high=30, medium=200, low=965),
        processing=ProcessingSummaryCounts(ocr_pending=3, ocr_failed=1, validation_pending=5, validation_failed=0),
    )

    with patch.object(
        AdminDashboardService, "get_admin_dashboard", new_callable=AsyncMock
    ) as mock_get:
        mock_get.return_value = mock_dashboard

        # 1. Super Admin access -> 200 OK
        app.dependency_overrides[get_current_user] = lambda: super_admin_user
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            res = await ac.get("/api/v1/admin/dashboard")
            assert res.status_code == 200
            data = res.json()
            assert data["areas"]["total"] == 10
            assert data["users"]["civilians"] == 1500
            assert data["cases"]["approved"] == 950
            assert data["risk"]["critical"] == 5
            assert data["processing"]["ocr_pending"] == 3

        # 2. Civilian access -> 403 Forbidden
        app.dependency_overrides[get_current_user] = lambda: civilian_user
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            res_civ = await ac.get("/api/v1/admin/dashboard")
            assert res_civ.status_code == 403

        # 3. Area Officer access -> 403 Forbidden
        app.dependency_overrides[get_current_user] = lambda: officer_a_user
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            res_off = await ac.get("/api/v1/admin/dashboard")
            assert res_off.status_code == 403

        app.dependency_overrides.clear()
