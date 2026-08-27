from unittest.mock import AsyncMock, patch
from httpx import ASGITransport, AsyncClient
import pytest

from app.api.dependencies import get_current_user
from app.main import app
from app.models.user import User
from app.schemas.admin_dashboard import (
    CaseStatisticsResponse,
    OfficerStatisticsResponse,
    ProcessingStatisticsResponse,
    ProofStatisticsResponse,
    ReviewStatisticsResponse,
    RiskStatisticsResponse,
)
from app.services.admin_dashboard_service import AdminDashboardService


@pytest.mark.anyio
async def test_admin_statistics_endpoints(super_admin_user: User) -> None:
    """Verify all statistical aggregation endpoints under /api/v1/admin/statistics."""
    mock_cases = CaseStatisticsResponse(total_cases=100, by_status={"approved": 80, "rejected": 20}, by_area={"North": 50, "South": 50})
    mock_risk = RiskStatisticsResponse(total_assessed=100, by_risk_level={"low": 70, "medium": 20, "high": 10}, average_risk_score=24.5)
    mock_reviews = ReviewStatisticsResponse(total_reviews=90, by_decision={"approve": 75, "reject": 15}, by_status={"completed": 90})
    mock_proofs = ProofStatisticsResponse(total_requests=25, by_status={"accepted": 20, "rejected": 5}, by_proof_type={"tax_receipt": 15, "mutation_deed": 10})
    mock_processing = ProcessingStatisticsResponse(total_jobs=120, by_status={"completed": 115, "failed": 5}, success_rate_percentage=95.83)
    mock_officers = OfficerStatisticsResponse(total_officers=10, assigned_officers=8, unassigned_officers=2, reviews_per_officer={"Officer 1": 40, "Officer 2": 50})

    with patch.object(AdminDashboardService, "get_case_statistics", new_callable=AsyncMock) as m_cases, \
         patch.object(AdminDashboardService, "get_risk_statistics", new_callable=AsyncMock) as m_risk, \
         patch.object(AdminDashboardService, "get_review_statistics", new_callable=AsyncMock) as m_rev, \
         patch.object(AdminDashboardService, "get_proof_statistics", new_callable=AsyncMock) as m_proofs, \
         patch.object(AdminDashboardService, "get_processing_statistics", new_callable=AsyncMock) as m_proc, \
         patch.object(AdminDashboardService, "get_officer_statistics", new_callable=AsyncMock) as m_off:

        m_cases.return_value = mock_cases
        m_risk.return_value = mock_risk
        m_rev.return_value = mock_reviews
        m_proofs.return_value = mock_proofs
        m_proc.return_value = mock_processing
        m_off.return_value = mock_officers

        app.dependency_overrides[get_current_user] = lambda: super_admin_user
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            r1 = await ac.get("/api/v1/admin/statistics/cases")
            assert r1.status_code == 200
            assert r1.json()["total_cases"] == 100

            r2 = await ac.get("/api/v1/admin/statistics/risk")
            assert r2.status_code == 200
            assert r2.json()["average_risk_score"] == 24.5

            r3 = await ac.get("/api/v1/admin/statistics/reviews")
            assert r3.status_code == 200
            assert r3.json()["total_reviews"] == 90

            r4 = await ac.get("/api/v1/admin/statistics/proofs")
            assert r4.status_code == 200
            assert r4.json()["total_requests"] == 25

            r5 = await ac.get("/api/v1/admin/statistics/processing")
            assert r5.status_code == 200
            assert r5.json()["success_rate_percentage"] == 95.83

            r6 = await ac.get("/api/v1/admin/statistics/officers")
            assert r6.status_code == 200
            assert r6.json()["total_officers"] == 10

        app.dependency_overrides.clear()
