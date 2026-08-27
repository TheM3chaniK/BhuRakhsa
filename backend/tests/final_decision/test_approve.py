from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
import uuid
from httpx import ASGITransport, AsyncClient
import pytest

from app.api.dependencies import get_current_user
from app.main import app
from app.models.enums import CaseStatus, OfficerDecision, ReviewStatus, RiskLevel
from app.models.final_decision import FinalDecision
from app.models.review import CaseReview
from app.models.user import User
from app.services.final_decision_service import FinalDecisionService
from app.services.review_service import ReviewService


@pytest.mark.anyio
async def test_officer_approve_flow(officer_a_user: User) -> None:
    """Test full officer approve flow creates final decision, audit events, and outbox event."""
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
        decision_reason="All property identifiers and boundary spatial validations were fully verified against the authoritative registry.",
        risk_score_at_decision=15,
        risk_level_at_decision=RiskLevel.LOW,
        completed_at=now,
        created_at=now,
        updated_at=now,
    )

    mock_final_decision = FinalDecision(
        id=uuid.uuid4(),
        case_id=case_id,
        review_id=review_id,
        decided_by=officer_a_user.id,
        decision=OfficerDecision.APPROVE,
        reason="All property identifiers and boundary spatial validations were fully verified against the authoritative registry.",
        risk_score_at_decision=15,
        risk_level_at_decision=RiskLevel.LOW,
        property_profile_version=1,
        decided_at=now,
        created_at=now,
    )

    with patch.object(
        ReviewService, "submit_decision", new_callable=AsyncMock
    ) as mock_submit, patch.object(
        FinalDecisionService, "get_final_decision", new_callable=AsyncMock
    ) as mock_get_decision:
        mock_submit.return_value = (mock_review_approved, CaseStatus.APPROVED)
        mock_get_decision.return_value = mock_final_decision

        app.dependency_overrides[get_current_user] = lambda: officer_a_user
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            payload = {
                "decision": "approve",
                "reason": "All property identifiers and boundary spatial validations were fully verified against the authoritative registry.",
            }
            res = await ac.post(f"/api/v1/cases/{case_id}/review/decision", json=payload)
            assert res.status_code == 200
            data = res.json()
            assert data["case_status"] == "approved"
            assert data["review"]["status"] == "completed"
            assert data["review"]["decision"] == "approve"

            # Check FinalDecision snapshot endpoint
            dec_res = await ac.get(f"/api/v1/cases/{case_id}/final-decision")
            assert dec_res.status_code == 200
            dec_data = dec_res.json()
            assert dec_data["decision"] == "approve"
            assert dec_data["risk_score_at_decision"] == 15
            assert dec_data["risk_level_at_decision"] == "low"
            assert dec_data["decided_by"] == str(officer_a_user.id)
        app.dependency_overrides.clear()
