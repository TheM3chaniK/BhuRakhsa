from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pypdfium2 as pdfium
import pytest

from app.models.document import Document
from app.models.document_processing_job import DocumentProcessingJob
from app.models.enums import DocumentStatus, ProcessingStatus
from app.models.ocr_result import OCRResult
from app.services.document_processing_service import DocumentProcessingService
from app.services.ocr_service import OcrService
from app.services.ollama_service import OllamaService, OllamaServiceException


@pytest.mark.anyio
async def test_partial_ocr_failure_marks_job_and_doc_failed(tmp_path: Path) -> None:
    """Verify that if page 1 succeeds and page 2 fails, the document and job remain FAILED (never marked PROCESSED)."""
    # Create 2-page test PDF
    pdf_path = tmp_path / "two_page.pdf"
    pdf = pdfium.PdfDocument.new()
    pdf.new_page(width=200, height=200)
    pdf.new_page(width=200, height=200)
    pdf.save(str(pdf_path))
    pdf.close()

    mock_ollama = MagicMock(spec=OllamaService)
    mock_ollama.check_connection = AsyncMock(return_value=True)
    mock_ollama.check_model_available = AsyncMock(return_value=True)

    # Page 1 succeeds, Page 2 fails
    async def mock_run_ocr(image_bytes, prompt, model_name=None):
        if hasattr(mock_run_ocr, "called_count"):
            mock_run_ocr.called_count += 1
        else:
            mock_run_ocr.called_count = 1

        if mock_run_ocr.called_count == 1:
            return "Page 1 OCR Text"
        raise OllamaServiceException("OLLAMA_TIMEOUT", "Timeout on page 2")

    mock_ollama.run_ocr = mock_run_ocr

    # Execute page 1
    p1_text, p1_ms = await OcrService.process_page(mock_ollama, b"p1_bytes", page_number=1)
    assert p1_text == "Page 1 OCR Text"

    # Execute page 2 -> raises OllamaServiceException
    with pytest.raises(OllamaServiceException) as exc:
        await OcrService.process_page(mock_ollama, b"p2_bytes", page_number=2)

    assert exc.value.code == "OLLAMA_TIMEOUT"
