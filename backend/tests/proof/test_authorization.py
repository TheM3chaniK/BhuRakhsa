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
async def test_proof_authorization_and_isolation(
    civilian_user: User, officer_a_user: User, officer_b_user: User, super_admin_user: User
) -> None:
    """Verify civilian only accesses own requests, officer is area-isolated, and super admin is global."""
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
        title="Title Clearance Certificate",
        description="Please provide certificate.",
        status=ProofRequestStatus.OPEN,
        due_at=None,
        created_at=now,
        updated_at=now,
        submissions=[],
    )

    with patch.object(
        ProofRequestService, "get_proof_request", new_callable=AsyncMock
    ) as mock_get_req, patch.object(
        ProofRequestService, "list_case_proof_requests", new_callable=AsyncMock
    ) as mock_list_reqs:

        mock_get_req.return_value = mock_req
        mock_list_reqs.return_value = [mock_req]

        # 1. Civilian accesses own request -> 200 OK
        app.dependency_overrides[get_current_user] = lambda: civilian_user
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            res_civ = await ac.get(f"/api/v1/proof-requests/{req_id}")
            assert res_civ.status_code == 200
            assert res_civ.json()["id"] == str(req_id)

            res_list = await ac.get(f"/api/v1/cases/{case_id}/proof-requests")
            assert res_list.status_code == 200
            assert len(res_list.json()) == 1

        # 2. Officer from outside area -> 403 Forbidden
        mock_get_req.side_effect = HTTPException(
            status_code=403,
            detail="You do not have permission to view this proof request.",
        )
        app.dependency_overrides[get_current_user] = lambda: officer_b_user
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            res_b = await ac.get(f"/api/v1/proof-requests/{req_id}")
            assert res_b.status_code == 403

        # 3. Super Admin accesses request anywhere -> 200 OK
        mock_get_req.side_effect = None
        app.dependency_overrides[get_current_user] = lambda: super_admin_user
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            res_admin = await ac.get(f"/api/v1/proof-requests/{req_id}")
            assert res_admin.status_code == 200

    app.dependency_overrides.clear()
