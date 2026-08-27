from datetime import datetime, timezone
import hashlib
from io import BytesIO
from unittest.mock import AsyncMock, patch
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_current_user
from app.main import app
from app.models.area import Area
from app.models.case import Case
from app.models.document import Document
from app.models.enums import CaseStatus, DocumentStatus, RiskLevel
from app.models.user import User
from app.services.document_service import DocumentService


@pytest.mark.anyio
async def test_upload_document_success(
    civilian_user: User, area_a: Area, tmp_path
) -> None:
    """Verify civilian successfully uploads a valid PDF document to own case."""
    now = datetime.now(timezone.utc)
    mock_case = Case(
        id=uuid.uuid4(),
        case_number="CASE-2026-000001",
        created_by=civilian_user.id,
        area_id=area_a.id,
        status=CaseStatus.DRAFT,
        risk_level=RiskLevel.UNKNOWN,
        title="Sample Case",
        created_at=now,
        updated_at=now,
    )

    pdf_content = b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF"
    pdf_sha256 = hashlib.sha256(pdf_content).hexdigest()

    mock_doc = Document(
        id=uuid.uuid4(),
        case_id=mock_case.id,
        original_filename="property_deed.pdf",
        stored_filename=f"{uuid.uuid4()}.pdf",
        mime_type="application/pdf",
        file_extension=".pdf",
        file_size=len(pdf_content),
        sha256_hash=pdf_sha256,
        storage_backend="local",
        storage_key=f"cases/{mock_case.id}/documents/{uuid.uuid4()}/original/sample.pdf",
        status=DocumentStatus.UPLOADED,
        uploaded_by=civilian_user.id,
        created_at=now,
        updated_at=now,
    )

    with patch.object(
        DocumentService, "upload_document", new_callable=AsyncMock
    ) as mock_upload:
        mock_upload.return_value = mock_doc

        app.dependency_overrides[get_current_user] = lambda: civilian_user
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            files = {"file": ("property_deed.pdf", BytesIO(pdf_content), "application/pdf")}
            res = await ac.post(f"/api/v1/cases/{mock_case.id}/documents", files=files)

            assert res.status_code == 201
            data = res.json()
            assert data["original_filename"] == "property_deed.pdf"
            assert data["mime_type"] == "application/pdf"
            assert data["file_extension"] == ".pdf"
            assert data["sha256_hash"] == pdf_sha256
            assert data["status"] == "uploaded"
            assert data["uploaded_by"] == str(civilian_user.id)
            assert "storage_key" not in data  # Internal path never exposed

    app.dependency_overrides.clear()
