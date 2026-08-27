from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
import uuid
import pytest
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_current_user
from app.main import app
from app.models.enums import ProofRequestStatus, ProofType
from app.models.proof_request import ProofRequest
from app.models.user import User
from app.services.proof_request_service import ProofRequestService


@pytest.mark.anyio
async def test_proof_status_transitions_accept_reject_cancel(
    officer_a_user: User, civilian_user: User
) -> None:
    """Verify accept, reject, and cancel status transitions on proof requests."""
    case_id = uuid.uuid4()
    req_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    mock_req_accepted = ProofRequest(
        id=req_id,
        case_id=case_id,
        requested_by=officer_a_user.id,
        requested_from=civilian_user.id,
        proof_type=ProofType.OWNERSHIP_DOCUMENT,
        title="Submit Registered Sale Deed",
        description="Please provide registered deed.",
        status=ProofRequestStatus.ACCEPTED,
        completed_at=now,
        created_at=now,
        updated_at=now,
        submissions=[],
    )

    mock_req_rejected = ProofRequest(
        id=req_id,
        case_id=case_id,
        requested_by=officer_a_user.id,
        requested_from=civilian_user.id,
        proof_type=ProofType.OWNERSHIP_DOCUMENT,
        title="Submit Registered Sale Deed",
        description="Please provide registered deed.",
        status=ProofRequestStatus.REJECTED,
        rejection_reason="The submitted document is missing the sub-registrar official stamp and seal.",
        completed_at=now,
        created_at=now,
        updated_at=now,
        submissions=[],
    )

    mock_req_cancelled = ProofRequest(
        id=req_id,
        case_id=case_id,
        requested_by=officer_a_user.id,
        requested_from=civilian_user.id,
        proof_type=ProofType.OWNERSHIP_DOCUMENT,
        title="Submit Registered Sale Deed",
        description="Please provide registered deed.",
        status=ProofRequestStatus.CANCELLED,
        cancellation_reason="Proof request is no longer needed after reference database sync.",
        completed_at=now,
        created_at=now,
        updated_at=now,
        submissions=[],
    )

    with patch.object(
        ProofRequestService, "accept_proof_request", new_callable=AsyncMock
    ) as mock_accept, patch.object(
        ProofRequestService, "reject_proof_request", new_callable=AsyncMock
    ) as mock_reject, patch.object(
        ProofRequestService, "cancel_proof_request", new_callable=AsyncMock
    ) as mock_cancel:

        mock_accept.return_value = mock_req_accepted
        mock_reject.return_value = mock_req_rejected
        mock_cancel.return_value = mock_req_cancelled

        app.dependency_overrides[get_current_user] = lambda: officer_a_user
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            # 1. Accept proof -> 200 OK (status = accepted)
            res_acc = await ac.post(f"/api/v1/proof-requests/{req_id}/accept")
            assert res_acc.status_code == 200
            assert res_acc.json()["status"] == "accepted"

            # 2. Reject proof -> 200 OK (status = rejected, reason recorded)
            res_rej = await ac.post(
                f"/api/v1/proof-requests/{req_id}/reject",
                json={"reason": "The submitted document is missing the sub-registrar official stamp and seal."},
            )
            assert res_rej.status_code == 200
            assert res_rej.json()["status"] == "rejected"
            assert res_rej.json()["rejection_reason"] is not None

            # 3. Cancel proof -> 200 OK (status = cancelled)
            res_can = await ac.post(
                f"/api/v1/proof-requests/{req_id}/cancel",
                json={"reason": "Proof request is no longer needed after reference database sync."},
            )
            assert res_can.status_code == 200
            assert res_can.json()["status"] == "cancelled"

    app.dependency_overrides.clear()
