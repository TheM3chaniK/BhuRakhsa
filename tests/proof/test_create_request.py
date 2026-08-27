from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
import uuid
from fastapi import HTTPException
import pytest
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_current_user
from app.main import app
from app.models.enums import ProofRequestStatus, ProofType
from app.models.proof_request import ProofRequest
from app.models.user import User
from app.services.proof_request_service import ProofRequestService


@pytest.mark.anyio
async def test_create_proof_request_endpoints(
    officer_a_user: User, officer_b_user: User, civilian_user: User
) -> None:
    """Verify Area Officer can create a proof request, validations are enforced, and unauthorized users are rejected."""
    case_id = uuid.uuid4()
    req_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    mock_req = ProofRequest(
        id=req_id,
        case_id=case_id,
        review_id=None,
        requested_by=officer_a_user.id,
        requested_from=civilian_user.id,
        proof_type=ProofType.OWNERSHIP_DOCUMENT,
        title="Submit Registered Sale Deed",
        description="Please upload the latest registered sale deed copy issued by the land sub-registry.",
        status=ProofRequestStatus.OPEN,
        due_at=None,
        created_at=now,
        updated_at=now,
    )

    with patch.object(
        ProofRequestService, "create_proof_request", new_callable=AsyncMock
    ) as mock_create:
        mock_create.return_value = mock_req

        # 1. Area Officer creates proof request -> 201 Created
        app.dependency_overrides[get_current_user] = lambda: officer_a_user
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            payload = {
                "title": "Submit Registered Sale Deed",
                "description": "Please upload the latest registered sale deed copy issued by the land sub-registry.",
                "proof_type": "ownership_document",
            }
            res = await ac.post(f"/api/v1/cases/{case_id}/proof-requests", json=payload)
            assert res.status_code == 201
            data = res.json()
            assert data["id"] == str(req_id)
            assert data["status"] == "open"
            assert data["proof_type"] == "ownership_document"

            # 2. Validation: short title or description -> 422 Unprocessable Entity
            payload_invalid = {
                "title": "ab",
                "description": "short",
                "proof_type": "ownership_document",
            }
            res_inv = await ac.post(
                f"/api/v1/cases/{case_id}/proof-requests", json=payload_invalid
            )
            assert res_inv.status_code == 422

        # 3. Civilian attempts to create request -> 403 Forbidden
        mock_create.side_effect = HTTPException(
            status_code=403,
            detail="Civilians cannot create proof requests.",
        )
        app.dependency_overrides[get_current_user] = lambda: civilian_user
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            res_civ = await ac.post(
                f"/api/v1/cases/{case_id}/proof-requests", json=payload
            )
            assert res_civ.status_code == 403

        # 4. Officer from wrong area -> 403 Forbidden
        mock_create.side_effect = HTTPException(
            status_code=403,
            detail="You do not have permission to access cases in this area.",
        )
        app.dependency_overrides[get_current_user] = lambda: officer_b_user
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            res_b = await ac.post(
                f"/api/v1/cases/{case_id}/proof-requests", json=payload
            )
            assert res_b.status_code == 403

    app.dependency_overrides.clear()
