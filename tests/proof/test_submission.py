from datetime import datetime, timezone
import io
from unittest.mock import AsyncMock, patch
import uuid
from fastapi import HTTPException
import pytest
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_current_user
from app.main import app
from app.models.enums import ProofSubmissionStatus
from app.models.proof_submission import ProofSubmission
from app.models.user import User
from app.services.proof_request_service import ProofRequestService


@pytest.mark.anyio
async def test_civilian_proof_submission_flow(
    civilian_user: User, officer_a_user: User
) -> None:
    """Verify civilian can submit proof document responding to open request, and non-civilians or unauthorized civilians are rejected."""
    req_id = uuid.uuid4()
    sub_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    mock_sub = ProofSubmission(
        id=sub_id,
        proof_request_id=req_id,
        submitted_by=civilian_user.id,
        document_id=doc_id,
        status=ProofSubmissionStatus.PROCESSING,
        comment="This is the latest registered copy issued by the land office.",
        submitted_at=now,
        created_at=now,
        updated_at=now,
    )

    with patch.object(
        ProofRequestService, "submit_proof", new_callable=AsyncMock
    ) as mock_submit:
        mock_submit.return_value = mock_sub

        # 1. Civilian uploads file -> 201 Created
        app.dependency_overrides[get_current_user] = lambda: civilian_user
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            files = {"file": ("deed.pdf", b"%PDF-1.4 test content", "application/pdf")}
            data = {"comment": "This is the latest registered copy issued by the land office."}
            res = await ac.post(
                f"/api/v1/proof-requests/{req_id}/submissions",
                files=files,
                data=data,
            )
            assert res.status_code == 201
            res_data = res.json()
            assert res_data["id"] == str(sub_id)
            assert res_data["proof_request_id"] == str(req_id)
            assert res_data["status"] == "processing"

        # 2. Submitting to non-open proof request -> 409 Conflict
        mock_submit.side_effect = HTTPException(
            status_code=409,
            detail="Proof request is not open for submission (current status: accepted).",
        )
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            res_conflict = await ac.post(
                f"/api/v1/proof-requests/{req_id}/submissions",
                files=files,
                data=data,
            )
            assert res_conflict.status_code == 409
            assert "not open for submission" in res_conflict.json()["detail"]

        # 3. Officer attempting to submit through civilian endpoint -> 403 Forbidden
        app.dependency_overrides[get_current_user] = lambda: officer_a_user
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            res_off = await ac.post(
                f"/api/v1/proof-requests/{req_id}/submissions",
                files=files,
                data=data,
            )
            assert res_off.status_code == 403

    app.dependency_overrides.clear()
