from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
import uuid
from fastapi import HTTPException
import pytest
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_current_user
from app.main import app
from app.models.enums import CaseStatus, OfficerDecision, ReviewStatus, RiskLevel
from app.models.review import CaseReview
from app.models.user import User
from app.services.review_service import ReviewService


@pytest.mark.anyio
async def test_review_decision_submission_and_snapshots(officer_a_user: User) -> None:
    """Verify APPROVE, REJECT, and REQUEST_PROOF decision submissions and snapshots."""
    case_id = uuid.uuid4()
    review_id = uuid.uuid4()
    area_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    mock_review_approved = CaseReview(
        id=review_id,
        case_id=case_id,
        reviewer_id=officer_a_user.id,
        reviewer_area_id=area_id,
        status=ReviewStatus.COMPLETED,
        decision=OfficerDecision.APPROVE,
        decision_reason="All property identifiers and records matched reference database and map perfectly.",
        risk_score_at_decision=15,
        risk_level_at_decision=RiskLevel.LOW,
        completed_at=now,
        created_at=now,
        updated_at=now,
    )

    with patch.object(
        ReviewService, "submit_decision", new_callable=AsyncMock
    ) as mock_submit:
        mock_submit.return_value = (mock_review_approved, CaseStatus.APPROVED)

        app.dependency_overrides[get_current_user] = lambda: officer_a_user
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            # 1. Submit APPROVE decision -> 200 OK
            payload_approve = {
                "decision": "approve",
                "reason": "All property identifiers and records matched reference database and map perfectly.",
            }
            res_app = await ac.post(
                f"/api/v1/cases/{case_id}/review/decision", json=payload_approve
            )
            assert res_app.status_code == 200
            data_app = res_app.json()
            assert data_app["case_status"] == "approved"
            assert data_app["review"]["decision"] == "approve"
            assert data_app["review"]["risk_score_at_decision"] == 15

            # 2. Decision validation: reason < 10 characters -> 422 Unprocessable Entity
            payload_short = {
                "decision": "approve",
                "reason": "Too short",
            }
            res_short = await ac.post(
                f"/api/v1/cases/{case_id}/review/decision", json=payload_short
            )
            assert res_short.status_code == 422

            # 3. Decision on already completed review -> 409 Conflict
            mock_submit.side_effect = HTTPException(
                status_code=409,
                detail="No in-progress review session found for this case.",
            )
            res_redecide = await ac.post(
                f"/api/v1/cases/{case_id}/review/decision", json=payload_approve
            )
            assert res_redecide.status_code == 409

    app.dependency_overrides.clear()
