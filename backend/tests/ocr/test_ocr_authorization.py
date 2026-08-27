from unittest.mock import AsyncMock, patch
import uuid

from fastapi import HTTPException
import pytest
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_current_user
from app.main import app
from app.models.user import User
from app.services.document_processing_service import DocumentProcessingService


@pytest.mark.anyio
async def test_ocr_endpoints_authorization(
    civilian_b_user: User, officer_b_user: User
) -> None:
    """Verify unauthorized civilian or officer outside case area receives 403 Forbidden."""
    doc_id = uuid.uuid4()

    with patch.object(
        DocumentProcessingService, "queue_document_processing", new_callable=AsyncMock
    ) as mock_queue, patch.object(
        DocumentProcessingService, "get_ocr_results", new_callable=AsyncMock
    ) as mock_ocr:

        mock_queue.side_effect = HTTPException(
            status_code=403,
            detail="You do not have permission to access this case.",
        )
        mock_ocr.side_effect = HTTPException(
            status_code=403,
            detail="You do not have permission to access this case.",
        )

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            # 1. Other civilian attempting to queue OCR -> 403 Forbidden
            app.dependency_overrides[get_current_user] = lambda: civilian_b_user
            res_civ_b = await ac.post(f"/api/v1/documents/{doc_id}/process")
            assert res_civ_b.status_code == 403

            # 2. Officer outside case area attempting to view OCR -> 403 Forbidden
            app.dependency_overrides[get_current_user] = lambda: officer_b_user
            res_off_b = await ac.get(f"/api/v1/documents/{doc_id}/ocr")
            assert res_off_b.status_code == 403

    app.dependency_overrides.clear()
