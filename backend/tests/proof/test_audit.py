from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
import uuid
import pytest
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_current_user
from app.main import app
from app.models.enums import ProofRequestAction, ProofRequestStatus
from app.models.proof_request_history import ProofRequestHistory
from app.models.user import User
from app.services.proof_request_service import ProofRequestService


@pytest.mark.anyio
async def test_proof_audit_history_retrieval(
    officer_a_user: User, civilian_user: User
) -> None:
    """Verify proof request audit history trail captures events with timestamps and actors."""
    req_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    mock_history = [
        ProofRequestHistory(
            id=uuid.uuid4(),
            proof_request_id=req_id,
            actor_id=officer_a_user.id,
            actor_type="user",
            action=ProofRequestAction.CREATED,
            old_status=None,
            new_status=ProofRequestStatus.OPEN,
            reason="Proof requested by officer.",
            created_at=now,
        ),
        ProofRequestHistory(
            id=uuid.uuid4(),
            proof_request_id=req_id,
            actor_id=civilian_user.id,
            actor_type="user",
            action=ProofRequestAction.SUBMITTED,
            old_status=ProofRequestStatus.OPEN,
            new_status=ProofRequestStatus.SUBMITTED,
            reason="Civilian submitted deed document.",
            created_at=now,
        ),
        ProofRequestHistory(
            id=uuid.uuid4(),
            proof_request_id=req_id,
            actor_id=None,
            actor_type="system",
            action=ProofRequestAction.PROCESSING_COMPLETED,
            old_status=ProofRequestStatus.SUBMITTED,
            new_status=ProofRequestStatus.SUBMITTED,
            reason="Processing & revalidation completed.",
            created_at=now,
        ),
        ProofRequestHistory(
            id=uuid.uuid4(),
            proof_request_id=req_id,
            actor_id=officer_a_user.id,
            actor_type="user",
            action=ProofRequestAction.ACCEPTED,
            old_status=ProofRequestStatus.SUBMITTED,
            new_status=ProofRequestStatus.ACCEPTED,
            reason="Proof accepted as sufficient.",
            created_at=now,
        ),
    ]

    with patch.object(
        ProofRequestService, "get_proof_request_history", new_callable=AsyncMock
    ) as mock_get_hist:
        mock_get_hist.return_value = mock_history

        app.dependency_overrides[get_current_user] = lambda: officer_a_user
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            res = await ac.get(f"/api/v1/proof-requests/{req_id}/history")
            assert res.status_code == 200
            data = res.json()
            assert len(data) == 4
            assert data[0]["action"] == "created"
            assert data[1]["action"] == "submitted"
            assert data[2]["action"] == "processing_completed"
            assert data[2]["actor_type"] == "system"
            assert data[3]["action"] == "accepted"

    app.dependency_overrides.clear()
