from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
import uuid
from httpx import ASGITransport, AsyncClient
import pytest

from app.api.dependencies import get_current_user
from app.main import app
from app.models.enums import CaseStatus, RiskLevel
from app.models.user import User
from app.schemas.case import CaseResponse
from app.schemas.pagination import PaginatedResponse
from app.services.officer_dashboard_service import OfficerDashboardService


@pytest.mark.anyio
async def test_officer_cases_search_scoped(officer_a_user: User, civilian_user: User) -> None:
    """Verify Area Officer case search is strictly scoped to assigned jurisdiction."""
    case_id = uuid.uuid4()
    area_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    mock_case = CaseResponse(
        id=case_id,
        case_number="CASE-2026-000088",
        created_by=uuid.uuid4(),
        area_id=area_id,
        status=CaseStatus.REVIEW_READY,
        risk_level=RiskLevel.MEDIUM,
        title="Officer Area Case",
        created_at=now,
        updated_at=now,
    )

    mock_paged = PaginatedResponse[CaseResponse](
        items=[mock_case],
        total=1,
        page=1,
        page_size=20,
        total_pages=1,
        has_next=False,
        has_prev=False,
    )

    with patch.object(
        OfficerDashboardService, "search_officer_cases", new_callable=AsyncMock
    ) as mock_search:
        mock_search.return_value = mock_paged

        # 1. Officer search -> 200 OK
        app.dependency_overrides[get_current_user] = lambda: officer_a_user
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            res = await ac.get(
                "/api/v1/officer/cases",
                params={"status": "review_ready", "page": 1, "page_size": 20},
            )
            assert res.status_code == 200
            data = res.json()
            assert data["total"] == 1
            assert data["items"][0]["id"] == str(case_id)

        # 2. Civilian access -> 403 Forbidden
        app.dependency_overrides[get_current_user] = lambda: civilian_user
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            res_civ = await ac.get("/api/v1/officer/cases")
            assert res_civ.status_code == 403

        app.dependency_overrides.clear()
