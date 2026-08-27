from io import BytesIO
from unittest.mock import AsyncMock, patch
import uuid

from fastapi import HTTPException
import pytest
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_current_user
from app.main import app
from app.models.user import User
from app.services.document_service import DocumentService


@pytest.mark.anyio
async def test_document_upload_authorization(
    civilian_user: User, civilian_b_user: User, officer_a_user: User
) -> None:
    """Verify authorization on POST /api/v1/cases/{case_id}/documents."""
    case_id = uuid.uuid4()
    pdf_content = b"%PDF-1.7 sample"

    with patch.object(
        DocumentService, "upload_document", new_callable=AsyncMock
    ) as mock_upload:
        mock_upload.side_effect = HTTPException(
            status_code=403,
            detail="You do not have permission to upload documents to this case.",
        )

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            files = {"file": ("deed.pdf", BytesIO(pdf_content), "application/pdf")}

            # 1. Other civilian attempting upload to another's case -> 403 Forbidden
            app.dependency_overrides[get_current_user] = lambda: civilian_b_user
            res_civ_b = await ac.post(f"/api/v1/cases/{case_id}/documents", files=files)
            assert res_civ_b.status_code == 403

            # 2. Area Officer attempting upload through civilian endpoint -> 403 Forbidden
            app.dependency_overrides[get_current_user] = lambda: officer_a_user
            res_off = await ac.post(f"/api/v1/cases/{case_id}/documents", files=files)
            assert res_off.status_code == 403

    app.dependency_overrides.clear()
