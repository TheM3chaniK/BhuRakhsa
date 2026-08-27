from datetime import datetime, timezone
import hashlib
from unittest.mock import AsyncMock, patch
import uuid

from fastapi import HTTPException
import pytest
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_current_user
from app.main import app
from app.models.document import Document
from app.models.enums import DocumentStatus
from app.models.user import User
from app.services.document_service import DocumentService


@pytest.mark.anyio
async def test_document_download_flow(
    civilian_user: User, civilian_b_user: User
) -> None:
    """Verify document download streaming and authorization."""
    now = datetime.now(timezone.utc)
    pdf_content = b"%PDF-1.7\nBinary Deed Content\n%%EOF"
    pdf_sha = hashlib.sha256(pdf_content).hexdigest()

    mock_doc = Document(
        id=uuid.uuid4(),
        case_id=uuid.uuid4(),
        original_filename="survey_map.pdf",
        stored_filename=f"{uuid.uuid4()}.pdf",
        mime_type="application/pdf",
        file_extension=".pdf",
        file_size=len(pdf_content),
        sha256_hash=pdf_sha,
        storage_backend="local",
        storage_key=f"cases/{uuid.uuid4()}/documents/{uuid.uuid4()}/original/survey_map.pdf",
        status=DocumentStatus.UPLOADED,
        uploaded_by=civilian_user.id,
        created_at=now,
        updated_at=now,
    )

    async def mock_stream():
        yield pdf_content

    with patch.object(
        DocumentService, "download_document", new_callable=AsyncMock
    ) as mock_dl:
        mock_dl.return_value = (mock_doc, mock_stream())

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            doc_id = str(mock_doc.id)

            # 1. Authorized download -> 200 OK
            app.dependency_overrides[get_current_user] = lambda: civilian_user
            res = await ac.get(f"/api/v1/documents/{doc_id}/download")
            assert res.status_code == 200
            assert res.content == pdf_content
            assert res.headers["content-type"] == "application/pdf"
            assert "survey_map.pdf" in res.headers["content-disposition"]
            assert res.headers["content-length"] == str(len(pdf_content))

            # 2. Unauthorized download -> 403 Forbidden
            mock_dl.side_effect = HTTPException(
                status_code=403,
                detail="You do not have permission to access this case.",
            )
            app.dependency_overrides[get_current_user] = lambda: civilian_b_user
            res_unauth = await ac.get(f"/api/v1/documents/{doc_id}/download")
            assert res_unauth.status_code == 403

    app.dependency_overrides.clear()
