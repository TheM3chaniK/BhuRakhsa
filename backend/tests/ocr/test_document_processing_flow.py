from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_current_user
from app.main import app
from app.models.document import Document
from app.models.document_processing_job import DocumentProcessingJob
from app.models.enums import DocumentStatus, ProcessingStatus
from app.models.ocr_result import OCRResult
from app.models.user import User
from app.services.document_processing_service import DocumentProcessingService


@pytest.mark.anyio
async def test_queue_and_inspect_document_ocr(civilian_user: User) -> None:
    """Verify document processing lifecycle: enqueue, get status, get OCR text."""
    doc_id = uuid.uuid4()
    job_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    mock_doc = Document(
        id=doc_id,
        case_id=uuid.uuid4(),
        original_filename="sample_deed.pdf",
        stored_filename=f"{doc_id}.pdf",
        mime_type="application/pdf",
        file_extension=".pdf",
        file_size=1024,
        sha256_hash="dummy_hash",
        storage_backend="local",
        storage_key=f"cases/c1/documents/{doc_id}/original/{doc_id}.pdf",
        status=DocumentStatus.QUEUED,
        uploaded_by=civilian_user.id,
        created_at=now,
        updated_at=now,
    )

    mock_job = DocumentProcessingJob(
        id=job_id,
        document_id=doc_id,
        status=ProcessingStatus.QUEUED,
        attempts=0,
        created_at=now,
        updated_at=now,
    )

    mock_ocr_results = [
        OCRResult(
            id=uuid.uuid4(),
            document_id=doc_id,
            page_number=1,
            text="LAND REGISTRY DEED\nSurvey Number: 108/2",
            model_name="deepseek-ocr",
            processing_time_ms=1250,
            created_at=now,
        ),
        OCRResult(
            id=uuid.uuid4(),
            document_id=doc_id,
            page_number=2,
            text="BOUNDARIES & DIMENSIONS\nNorth: Road\nSouth: Plot 109",
            model_name="deepseek-ocr",
            processing_time_ms=1100,
            created_at=now,
        ),
    ]

    with patch.object(
        DocumentProcessingService, "queue_document_processing", new_callable=AsyncMock
    ) as mock_queue, patch.object(
        DocumentProcessingService, "get_processing_status", new_callable=AsyncMock
    ) as mock_status, patch.object(
        DocumentProcessingService, "get_ocr_results", new_callable=AsyncMock
    ) as mock_results:

        mock_queue.return_value = (mock_doc, mock_job)
        mock_status.return_value = (mock_doc, mock_job)
        mock_results.return_value = (mock_doc, mock_ocr_results)

        app.dependency_overrides[get_current_user] = lambda: civilian_user
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            # 1. Enqueue document for processing -> 202 Accepted
            res_queue = await ac.post(f"/api/v1/documents/{doc_id}/process")
            assert res_queue.status_code == 202
            data_queue = res_queue.json()
            assert data_queue["document_id"] == str(doc_id)
            assert data_queue["job_id"] == str(job_id)
            assert data_queue["document_status"] == "queued"
            assert data_queue["processing_status"] == "queued"

            # 2. Check processing status -> 200 OK
            res_stat = await ac.get(f"/api/v1/documents/{doc_id}/processing")
            assert res_stat.status_code == 200
            data_stat = res_stat.json()
            assert data_stat["document_id"] == str(doc_id)
            assert data_stat["processing"]["job_id"] == str(job_id)
            assert data_stat["processing"]["status"] == "queued"

            # 3. Retrieve OCR results -> 200 OK
            res_ocr = await ac.get(f"/api/v1/documents/{doc_id}/ocr")
            assert res_ocr.status_code == 200
            data_ocr = res_ocr.json()
            assert data_ocr["document_id"] == str(doc_id)
            assert len(data_ocr["pages"]) == 2
            assert data_ocr["pages"][0]["page_number"] == 1
            assert "LAND REGISTRY" in data_ocr["pages"][0]["text"]
            assert data_ocr["pages"][1]["page_number"] == 2

    app.dependency_overrides.clear()
