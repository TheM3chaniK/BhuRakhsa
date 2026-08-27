from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
import uuid
from httpx import ASGITransport, AsyncClient
import pytest

from app.api.dependencies import get_current_user
from app.main import app
from app.models.enums import CaseStatus, RiskLevel
from app.models.user import User
from app.schemas.admin_dashboard import AdminCaseDetailResponse
from app.schemas.case import CaseResponse
from app.schemas.pagination import PaginatedResponse
from app.services.admin_dashboard_service import AdminDashboardService


@pytest.mark.anyio
async def test_admin_case_search_and_360_detail(super_admin_user: User) -> None:
    """Verify admin case search and full 360-degree operational detail retrieval."""
    case_id = uuid.uuid4()
    area_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    mock_case_resp = CaseResponse(
        id=case_id,
        case_number="CASE-2026-000042",
        created_by=uuid.uuid4(),
        area_id=area_id,
        status=CaseStatus.APPROVED,
        risk_level=RiskLevel.LOW,
        title="Admin Test Property",
        description="Sample description",
        created_at=now,
        updated_at=now,
    )

    mock_paged = PaginatedResponse[CaseResponse](
        items=[mock_case_resp],
        total=1,
        page=1,
        page_size=20,
        total_pages=1,
        has_next=False,
        has_prev=False,
    )

    mock_detail = AdminCaseDetailResponse(
        case=mock_case_resp,
        property_profile=None,
        documents=[],
        ocr_pages=[],
        extracted_fields=[],
        database_validation_runs=[],
        gis_validation_runs=[],
        mismatches=[],
        risk_assessments=[],
        reviews=[],
        proof_requests=[],
        final_decision=None,
        audit_events=[],
    )

    with patch.object(
        AdminDashboardService, "search_cases", new_callable=AsyncMock
    ) as mock_search, patch.object(
        AdminDashboardService, "get_admin_case_detail", new_callable=AsyncMock
    ) as mock_get_detail:

        mock_search.return_value = mock_paged
        mock_get_detail.return_value = mock_detail

        app.dependency_overrides[get_current_user] = lambda: super_admin_user
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            # 1. Search cases with filters
            res_search = await ac.get(
                "/api/v1/admin/cases",
                params={"status": "approved", "risk_level": "low", "page": 1, "page_size": 20},
            )
            assert res_search.status_code == 200
            search_data = res_search.json()
            assert search_data["total"] == 1
            assert search_data["items"][0]["case_number"] == "CASE-2026-000042"

            # 2. Get 360-degree case detail
            res_detail = await ac.get(f"/api/v1/admin/cases/{case_id}")
            assert res_detail.status_code == 200
            detail_data = res_detail.json()
            assert detail_data["case"]["id"] == str(case_id)
            assert detail_data["case"]["status"] == "approved"

        app.dependency_overrides.clear()
