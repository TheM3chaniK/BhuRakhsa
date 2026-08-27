from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

from fastapi import HTTPException
import pytest
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_current_user
from app.main import app
from app.models.document import Document
from app.models.enums import DocumentStatus, ExtractionStatus, ProcessingStatus
from app.models.evidence import Evidence
from app.models.extraction import ExtractedField
from app.models.extraction_job import ExtractionJob
from app.models.ocr_result import OCRResult
from app.models.user import User
from app.schemas.extraction import (
    DocumentEvidenceResponse,
    DocumentExtractionResponse,
    EvidenceItemResponse,
    ExtractedFieldResponse,
    FieldEvidenceGroupResponse,
    LLMExtractedFieldItem,
    LLMExtractionOutput,
)
from app.services.extraction_service import ExtractionService


@pytest.mark.anyio
async def test_extraction_api_endpoints_flow(civilian_user: User) -> None:
    """Verify structured field extraction API endpoints: queue 202, get fields, get evidence."""
    doc_id = uuid.uuid4()
    job_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    mock_doc = AsyncMock()
    mock_doc.id = doc_id
    mock_doc.status = DocumentStatus.PROCESSED

    mock_job = AsyncMock()
    mock_job.id = job_id
    mock_job.status = ProcessingStatus.QUEUED

    mock_extraction_res = DocumentExtractionResponse(
        document_id=doc_id,
        status="completed",
        fields=[
            ExtractedFieldResponse(
                id=uuid.uuid4(),
                document_id=doc_id,
                field_name="owner_name",
                field_value="Ramesh Kumar",
                normalized_value="ramesh kumar",
                confidence=0.95,
                status=ExtractionStatus.EXTRACTED,
                extractor_version="1.0",
                created_at=now,
            ),
            ExtractedFieldResponse(
                id=uuid.uuid4(),
                document_id=doc_id,
                field_name="survey_number",
                field_value="123/45",
                normalized_value="123/45",
                confidence=0.92,
                status=ExtractionStatus.EXTRACTED,
                extractor_version="1.0",
                created_at=now,
            ),
            ExtractedFieldResponse(
                id=uuid.uuid4(),
                document_id=doc_id,
                field_name="registration_date",
                field_value="12/03/2025",
                normalized_value="2025-03-12",
                confidence=0.88,
                status=ExtractionStatus.EXTRACTED,
                extractor_version="1.0",
                created_at=now,
            ),
        ],
    )

    mock_evidence_res = DocumentEvidenceResponse(
        document_id=doc_id,
        fields=[
            FieldEvidenceGroupResponse(
                field_name="owner_name",
                field_value="Ramesh Kumar",
                confidence=0.95,
                status=ExtractionStatus.EXTRACTED,
                evidence=[
                    EvidenceItemResponse(
                        id=uuid.uuid4(),
                        page_number=1,
                        source_text="Owner: Ramesh Kumar",
                        created_at=now,
                    )
                ],
            )
        ],
    )

    with patch.object(
        ExtractionService, "queue_extraction", new_callable=AsyncMock
    ) as mock_queue, patch.object(
        ExtractionService, "get_extraction_results", new_callable=AsyncMock
    ) as mock_get_ext, patch.object(
        ExtractionService, "get_document_evidence", new_callable=AsyncMock
    ) as mock_get_ev:

        mock_queue.return_value = (mock_doc, mock_job)
        mock_get_ext.return_value = mock_extraction_res
        mock_get_ev.return_value = mock_evidence_res

        app.dependency_overrides[get_current_user] = lambda: civilian_user
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            # 1. Enqueue extraction -> 202 Accepted
            res_queue = await ac.post(f"/api/v1/documents/{doc_id}/extract")
            assert res_queue.status_code == 202
            data_queue = res_queue.json()
            assert data_queue["document_id"] == str(doc_id)
            assert data_queue["job_id"] == str(job_id)
            assert data_queue["status"] == "queued"

            # 2. Get structured extraction fields -> 200 OK
            res_ext = await ac.get(f"/api/v1/documents/{doc_id}/extraction")
            assert res_ext.status_code == 200
            data_ext = res_ext.json()
            assert len(data_ext["fields"]) == 3
            assert data_ext["fields"][0]["field_name"] == "owner_name"
            assert data_ext["fields"][0]["normalized_value"] == "ramesh kumar"
            assert data_ext["fields"][2]["normalized_value"] == "2025-03-12"

            # 3. Get grounded evidence links -> 200 OK
            res_ev = await ac.get(f"/api/v1/documents/{doc_id}/evidence")
            assert res_ev.status_code == 200
            data_ev = res_ev.json()
            assert len(data_ev["fields"]) == 1
            assert data_ev["fields"][0]["evidence"][0]["page_number"] == 1
            assert "Ramesh Kumar" in data_ev["fields"][0]["evidence"][0]["source_text"]

            # 4. Conflict error when OCR is not complete -> 409 Conflict
            mock_queue.side_effect = HTTPException(
                status_code=409,
                detail="OCR processing has not completed for this document.",
            )
            res_unproc = await ac.post(f"/api/v1/documents/{doc_id}/extract")
            assert res_unproc.status_code == 409

    app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_anti_hallucination_and_filtering() -> None:
    """Verify that hallucinated field names, invalid page numbers, and ungrounded source citations are safely rejected."""
    raw_llm_output = LLMExtractionOutput(
        fields=[
            # Valid field & grounded evidence
            LLMExtractedFieldItem(
                field_name="owner_name",
                value="Ramesh Kumar",
                confidence=0.95,
                page_number=1,
                source_text="Owner: Ramesh Kumar",
            ),
            # Unregistered field name -> should be skipped
            LLMExtractedFieldItem(
                field_name="imaginary_fake_field",
                value="Fake",
                confidence=0.90,
                page_number=1,
                source_text="Owner: Ramesh Kumar",
            ),
            # Invalid page number (Page 99 on 1-page document) -> should be skipped
            LLMExtractedFieldItem(
                field_name="survey_number",
                value="999/99",
                confidence=0.90,
                page_number=99,
                source_text="Survey: 999/99",
            ),
            # Ungrounded source text (text doesn't exist on page 1) -> evidence discarded
            LLMExtractedFieldItem(
                field_name="property_address",
                value="Fake Street 42",
                confidence=0.50,
                page_number=1,
                source_text="Non-existent snippet in document",
            ),
            # Missing field
            LLMExtractedFieldItem(
                field_name="ward",
                value="NOT_FOUND",
                confidence=0.0,
                page_number=1,
                source_text="",
            ),
        ]
    )

    page_map = {
        1: OCRResult(
            id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            page_number=1,
            text="LAND TITLE DEED\nOwner: Ramesh Kumar\nSurvey No: 123/45",
            model_name="deepseek-ocr",
            processing_time_ms=1000,
        )
    }

    # Verify field 0 (valid)
    assert (
        ExtractionService.verify_source_text_grounding(
            page_map[1].text, raw_llm_output.fields[0].source_text
        )
        is True
    )

    # Verify field 3 (ungrounded)
    assert (
        ExtractionService.verify_source_text_grounding(
            page_map[1].text, raw_llm_output.fields[3].source_text
        )
        is False
    )
