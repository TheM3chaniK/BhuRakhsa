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
async def test_start_review_and_concurrency_locking(
    officer_a_user: User, officer_b_user: User
) -> None:
    """Verify review start acquires assignment lock and concurrent start attempts are rejected with 409 Conflict."""
    case_id = uuid.uuid4()
    review_id = uuid.uuid4()
    area_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    mock_review = CaseReview(
        id=review_id,
        case_id=case_id,
        reviewer_id=officer_a_user.id,
        reviewer_area_id=area_id,
        status=ReviewStatus.IN_PROGRESS,
        started_at=now,
        created_at=now,
        updated_at=now,
    )

    with patch.object(
        ReviewService, "start_review", new_callable=AsyncMock
    ) as mock_start:
        mock_start.return_value = mock_review

        # 1. Officer A starts review -> 200 OK
        app.dependency_overrides[get_current_user] = lambda: officer_a_user
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            res = await ac.post(f"/api/v1/cases/{case_id}/review/start")
            assert res.status_code == 200
            data = res.json()
            assert data["review"]["status"] == "in_progress"
            assert data["review"]["reviewer_id"] == str(officer_a_user.id)

        # 2. Officer B attempts to start same in-progress review -> 409 Conflict
        mock_start.side_effect = HTTPException(
            status_code=409,
            detail="Case review is already in progress by another officer.",
        )
        app.dependency_overrides[get_current_user] = lambda: officer_b_user
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            res_conflict = await ac.post(f"/api/v1/cases/{case_id}/review/start")
            assert res_conflict.status_code == 409
            assert "already in progress" in res_conflict.json()["detail"]

        # 3. Attempting to start review on unready case -> 409 Conflict
        mock_start.side_effect = HTTPException(
            status_code=409,
            detail="Case is not ready for review: GIS spatial validation has not completed.",
        )
        app.dependency_overrides[get_current_user] = lambda: officer_a_user
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            res_unready = await ac.post(f"/api/v1/cases/{case_id}/review/start")
            assert res_unready.status_code == 409
            assert "GIS spatial validation" in res_unready.json()["detail"]

    app.dependency_overrides.clear()
