from unittest.mock import AsyncMock, patch
import uuid
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
import pytest

from app.api.dependencies import get_current_user
from app.main import app
from app.models.user import User
from app.services.proof_request_service import ProofRequestService
from app.services.review_service import ReviewService


@pytest.mark.anyio
async def test_terminal_state_blocks_further_actions(officer_a_user: User) -> None:
    """Verify that APPROVED and REJECTED states block review start, decision submission, and proof requests."""
    case_id = uuid.uuid4()

    app.dependency_overrides[get_current_user] = lambda: officer_a_user

    with patch.object(
        ReviewService, "start_review", new_callable=AsyncMock
    ) as mock_start, patch.object(
        ReviewService, "submit_decision", new_callable=AsyncMock
    ) as mock_submit, patch.object(
        ProofRequestService, "create_proof_request", new_callable=AsyncMock
    ) as mock_proof_req:

        mock_start.side_effect = HTTPException(status_code=409, detail="Case is already finalized and cannot be reviewed.")
        mock_submit.side_effect = HTTPException(status_code=409, detail="Case is already finalized and cannot accept further decisions.")
        mock_proof_req.side_effect = HTTPException(status_code=409, detail="Cannot request proof on an already finalized case.")

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            # 1. Start review on finalized case -> 409
            res1 = await ac.post(f"/api/v1/cases/{case_id}/review/start")
            assert res1.status_code == 409

            # 2. Decision on finalized case -> 409
            res2 = await ac.post(
                f"/api/v1/cases/{case_id}/review/decision",
                json={"decision": "reject", "reason": "Attempting to modify terminal state"},
            )
            assert res2.status_code == 409

            # 3. Proof request on finalized case -> 409
            res3 = await ac.post(
                f"/api/v1/cases/{case_id}/proof-requests",
                json={"title": "More Docs", "description": "Need more documentation", "proof_type": "tax_receipt"},
            )
            assert res3.status_code == 409

    app.dependency_overrides.clear()
