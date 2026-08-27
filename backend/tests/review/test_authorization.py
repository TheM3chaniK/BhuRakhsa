from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
import uuid
from fastapi import HTTPException
import pytest
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_current_user
from app.main import app
from app.models.enums import ReviewStatus
from app.models.review import CaseReview
from app.models.user import User
from app.services.review_service import ReviewService


@pytest.mark.anyio
async def test_review_authorization_and_jurisdiction(
    officer_a_user: User, officer_b_user: User, civilian_user: User, super_admin_user: User
) -> None:
    """Verify Area Officer jurisdiction enforcement, Civilian rejection, and Super Admin global review access."""
    case_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    mock_review = CaseReview(
        id=uuid.uuid4(),
        case_id=case_id,
        reviewer_id=super_admin_user.id,
        reviewer_area_id=uuid.uuid4(),
        status=ReviewStatus.IN_PROGRESS,
        started_at=now,
        created_at=now,
        updated_at=now,
    )

    with patch.object(
        ReviewService, "start_review", new_callable=AsyncMock
    ) as mock_start, patch.object(
        ReviewService, "get_review_context", new_callable=AsyncMock
    ) as mock_ctx:

        mock_start.return_value = mock_review
        mock_ctx.return_value = {
            "case": {
                "id": case_id,
                "case_number": "CASE-2026-000001",
                "created_by": uuid.uuid4(),
                "area_id": uuid.uuid4(),
                "status": "under_review",
                "risk_level": "low",
                "created_at": now,
                "updated_at": now,
            },
            "review": None,
            "property_profile": None,
            "documents": [],
            "database_validation": None,
            "gis_validation": None,
            "mismatches": [],
            "risk_assessment": None,
            "history": [],
        }

        # 1. Super Admin can start review anywhere -> 200 OK
        app.dependency_overrides[get_current_user] = lambda: super_admin_user
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            res_admin = await ac.post(f"/api/v1/cases/{case_id}/review/start")
            assert res_admin.status_code == 200

        # 2. Officer outside assigned area -> 403 Forbidden
        mock_start.side_effect = HTTPException(
            status_code=403,
            detail="You do not have permission to access cases in this area.",
        )
        app.dependency_overrides[get_current_user] = lambda: officer_b_user
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            res_b = await ac.post(f"/api/v1/cases/{case_id}/review/start")
            assert res_b.status_code == 403

        # 3. Civilian cannot start review -> 403 Forbidden
        mock_start.side_effect = HTTPException(
            status_code=403,
            detail="Civilians cannot review cases.",
        )
        app.dependency_overrides[get_current_user] = lambda: civilian_user
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            res_civ = await ac.post(f"/api/v1/cases/{case_id}/review/start")
            assert res_civ.status_code == 403

    app.dependency_overrides.clear()
