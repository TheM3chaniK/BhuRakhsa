from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
import uuid
import pytest
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_current_user
from app.main import app
from app.models.enums import CaseStatus, OfficerDecision, ProofRequestStatus, ProofType, ReviewStatus, RiskLevel
from app.models.proof_request import ProofRequest
from app.models.review import CaseReview
from app.models.user import User
from app.services.proof_request_service import ProofRequestService
from app.services.review_service import ReviewService


@pytest.mark.anyio
async def test_full_proof_review_cycle(
    officer_a_user: User, civilian_user: User
) -> None:
    """Verify complete review cycle: Review 1 -> Request Proof -> Proof Upload & Accept -> Review 2 -> Approve."""
    case_id = uuid.uuid4()
    req_id = uuid.uuid4()
    rev1_id = uuid.uuid4()
    rev2_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    # Review 1 ends with REQUEST_PROOF
    mock_rev1 = CaseReview(
        id=rev1_id,
        case_id=case_id,
        reviewer_id=officer_a_user.id,
        reviewer_area_id=uuid.uuid4(),
        status=ReviewStatus.COMPLETED,
        decision=OfficerDecision.REQUEST_PROOF,
        decision_reason="Submitted document is blurry and missing owner registry page.",
        completed_at=now,
        created_at=now,
        updated_at=now,
    )

    # Proof request created
    mock_req = ProofRequest(
        id=req_id,
        case_id=case_id,
        review_id=rev1_id,
        requested_by=officer_a_user.id,
        requested_from=civilian_user.id,
        proof_type=ProofType.OWNERSHIP_DOCUMENT,
        title="Clear Copy of Title Deed",
        description="Please provide legible copy of deed.",
        status=ProofRequestStatus.OPEN,
        created_at=now,
        updated_at=now,
        submissions=[],
    )

    # Review 2 starts and completes with APPROVE
    mock_rev2 = CaseReview(
        id=rev2_id,
        case_id=case_id,
        reviewer_id=officer_a_user.id,
        reviewer_area_id=uuid.uuid4(),
        status=ReviewStatus.COMPLETED,
        decision=OfficerDecision.APPROVE,
        decision_reason="New registered sale deed provided matches reference database perfectly.",
        risk_score_at_decision=10,
        risk_level_at_decision=RiskLevel.LOW,
        completed_at=now,
        created_at=now,
        updated_at=now,
    )

    with patch.object(
        ReviewService, "submit_decision", new_callable=AsyncMock
    ) as mock_decide, patch.object(
        ProofRequestService, "create_proof_request", new_callable=AsyncMock
    ) as mock_create_req, patch.object(
        ProofRequestService, "accept_proof_request", new_callable=AsyncMock
    ) as mock_accept_req:

        # 1. Officer submits REQUEST_PROOF on Review 1
        mock_decide.return_value = (mock_rev1, CaseStatus.PROOF_REQUIRED)
        app.dependency_overrides[get_current_user] = lambda: officer_a_user
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            res_dec1 = await ac.post(
                f"/api/v1/cases/{case_id}/review/decision",
                json={
                    "decision": "request_proof",
                    "reason": "Submitted document is blurry and missing owner registry page.",
                },
            )
            assert res_dec1.status_code == 200
            assert res_dec1.json()["case_status"] == "proof_required"

            # 2. Officer creates specific ProofRequest
            mock_create_req.return_value = mock_req
            res_req = await ac.post(
                f"/api/v1/cases/{case_id}/proof-requests",
                json={
                    "title": "Clear Copy of Title Deed",
                    "description": "Please provide legible copy of deed.",
                    "proof_type": "ownership_document",
                    "review_id": str(rev1_id),
                },
            )
            assert res_req.status_code == 201
            assert res_req.json()["status"] == "open"

            # 3. Proof reviewed and accepted
            mock_req.status = ProofRequestStatus.ACCEPTED
            mock_accept_req.return_value = mock_req
            res_acc = await ac.post(f"/api/v1/proof-requests/{req_id}/accept")
            assert res_acc.status_code == 200
            assert res_acc.json()["status"] == "accepted"

            # 4. Review 2 approves case
            mock_decide.return_value = (mock_rev2, CaseStatus.APPROVED)
            res_dec2 = await ac.post(
                f"/api/v1/cases/{case_id}/review/decision",
                json={
                    "decision": "approve",
                    "reason": "New registered sale deed provided matches reference database perfectly.",
                },
            )
            assert res_dec2.status_code == 200
            assert res_dec2.json()["case_status"] == "approved"

    app.dependency_overrides.clear()
