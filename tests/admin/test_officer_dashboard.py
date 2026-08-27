from unittest.mock import AsyncMock, patch
import uuid
from httpx import ASGITransport, AsyncClient
import pytest

from app.api.dependencies import get_current_user
from app.main import app
from app.models.user import User
from app.schemas.admin_dashboard import (
    CaseSummaryCounts,
    OfficerDashboardResponse,
    RiskSummaryCounts,
)
from app.services.officer_dashboard_service import OfficerDashboardService


@pytest.mark.anyio
async def test_officer_dashboard_metrics(officer_a_user: User, civilian_user: User) -> None:
    """Verify Area Officer dashboard returns area-scoped counts and rejects civilians."""
    area_id = uuid.uuid4()
    mock_officer_dashboard = OfficerDashboardResponse(
        assigned_areas=[area_id],
        cases=CaseSummaryCounts(total=45, under_review=5, proof_required=2, approved=30, rejected=8),
        risk=RiskSummaryCounts(critical=0, high=4, medium=15, low=26),
        queue={"review_ready": 3, "in_progress": 2, "proof_submitted": 1},
    )

    with patch.object(
        OfficerDashboardService, "get_officer_dashboard", new_callable=AsyncMock
    ) as mock_get:
        mock_get.return_value = mock_officer_dashboard

        # 1. Officer access -> 200 OK
        app.dependency_overrides[get_current_user] = lambda: officer_a_user
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            res = await ac.get("/api/v1/officer/dashboard")
            assert res.status_code == 200
            data = res.json()
            assert len(data["assigned_areas"]) == 1
            assert data["cases"]["total"] == 45
            assert data["queue"]["review_ready"] == 3

        # 2. Civilian access -> 403 Forbidden
        app.dependency_overrides[get_current_user] = lambda: civilian_user
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            res_civ = await ac.get("/api/v1/officer/dashboard")
            assert res_civ.status_code == 403

        app.dependency_overrides.clear()
