from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
import uuid
import pytest
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_current_user
from app.main import app
from app.models.enums import (
    CaseStatus,
    OfficerDecision,
    ReviewAction,
    ReviewStatus,
    RiskAssessmentStatus,
    RiskLevel,
)
from app.models.review_history import ReviewHistory
from app.models.user import User
from app.schemas.case import CaseResponse
from app.schemas.review import (
    CaseReviewResponse,
    ReviewDetailResponse,
    ReviewHistoryResponse,
)
from app.services.review_service import ReviewService


@pytest.mark.anyio
async def test_review_context_and_history_endpoints(officer_a_user: User) -> None:
    """Verify holistic review context retrieval and audit trail history endpoint."""
    case_id = uuid.uuid4()
    review_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    mock_context_dict = {
        "case": {
            "id": case_id,
            "case_number": "CASE-2026-000001",
            "created_by": uuid.uuid4(),
            "area_id": uuid.uuid4(),
            "status": "under_review",
            "risk_level": "high",
            "title": "Plot 7 Verification",
            "description": None,
            "created_at": now,
            "updated_at": now,
            "submitted_at": now,
            "reviewed_at": None,
            "reviewed_by": officer_a_user.id,
        },
        "review": {
            "id": review_id,
            "case_id": case_id,
            "reviewer_id": officer_a_user.id,
            "reviewer_area_id": uuid.uuid4(),
            "status": "in_progress",
            "started_at": now,
            "completed_at": None,
            "decision": None,
            "decision_reason": None,
            "risk_score_at_decision": None,
            "risk_level_at_decision": None,
            "created_at": now,
            "updated_at": now,
        },
        "property_profile": None,
        "documents": [],
        "database_validation": None,
        "gis_validation": None,
        "mismatches": [],
        "risk_assessment": None,
        "history": [
            {
                "id": uuid.uuid4(),
                "case_id": case_id,
                "review_id": review_id,
                "actor_id": officer_a_user.id,
                "action": "review_started",
                "old_status": "not_started",
                "new_status": "in_progress",
                "old_decision": None,
                "new_decision": None,
                "reason": "Review started.",
                "created_at": now,
            }
        ],
    }

    mock_history_item = ReviewHistory(
        id=uuid.uuid4(),
        case_id=case_id,
        review_id=review_id,
        actor_id=officer_a_user.id,
        action=ReviewAction.REVIEW_STARTED,
        old_status=ReviewStatus.NOT_STARTED,
        new_status=ReviewStatus.IN_PROGRESS,
        reason="Review started.",
        created_at=now,
    )

    with patch.object(
        ReviewService, "get_review_context", new_callable=AsyncMock
    ) as mock_get_ctx, patch.object(
        ReviewService, "get_review_history", new_callable=AsyncMock
    ) as mock_get_hist:

        mock_get_ctx.return_value = mock_context_dict
        mock_get_hist.return_value = [mock_history_item]

        app.dependency_overrides[get_current_user] = lambda: officer_a_user
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            # 1. Get holistic review context -> 200 OK
            res_ctx = await ac.get(f"/api/v1/cases/{case_id}/review")
            assert res_ctx.status_code == 200
            data_ctx = res_ctx.json()
            assert data_ctx["case"]["case_number"] == "CASE-2026-000001"
            assert data_ctx["review"]["status"] == "in_progress"
            assert len(data_ctx["history"]) == 1

            # 2. Get review audit history -> 200 OK
            res_h = await ac.get(f"/api/v1/cases/{case_id}/review/history")
            assert res_h.status_code == 200
            data_h = res_h.json()
            assert len(data_h) == 1
            assert data_h[0]["action"] == "review_started"

    app.dependency_overrides.clear()
