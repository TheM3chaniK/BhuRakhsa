from pathlib import Path
from PIL import Image
import pypdfium2 as pdfium
import pytest

from app.core.config import settings
from app.services.ocr_service import OcrService
from app.services.ollama_service import OllamaServiceException


def test_preprocess_pdf_multi_page(tmp_path: Path) -> None:
    """Verify that a multi-page PDF is rendered into individual PNG image byte buffers."""
    pdf_path = tmp_path / "test_deed.pdf"

    pdf = pdfium.PdfDocument.new()
    pdf.new_page(width=300, height=400)
    pdf.new_page(width=300, height=400)
    pdf.save(str(pdf_path))
    pdf.close()

    pages = OcrService.preprocess_document_to_pages(pdf_path, ".pdf")
    assert len(pages) == 2
    assert all(isinstance(p, bytes) and len(p) > 0 for p in pages)
    # Check PNG signature for each page
    assert all(p.startswith(b"\x89PNG\r\n\x1a\n") for p in pages)


def test_preprocess_image(tmp_path: Path) -> None:
    """Verify JPEG and PNG image normalization."""
    img_path = tmp_path / "survey.jpg"
    img = Image.new("RGB", (200, 200), color="white")
    img.save(img_path, format="JPEG")

    pages = OcrService.preprocess_document_to_pages(img_path, ".jpg")
    assert len(pages) == 1
    assert pages[0].startswith(b"\x89PNG\r\n\x1a\n")


def test_preprocess_page_limit_enforcement(tmp_path: Path, monkeypatch) -> None:
    """Verify that documents with pages exceeding MAX_DOCUMENT_PAGES raise an exception."""
    monkeypatch.setattr(settings, "MAX_DOCUMENT_PAGES", 2)

    pdf_path = tmp_path / "oversized.pdf"
    pdf = pdfium.PdfDocument.new()
    pdf.new_page(width=100, height=100)
    pdf.new_page(width=100, height=100)
    pdf.new_page(width=100, height=100)  # 3 pages > 2 limit
    pdf.save(str(pdf_path))
    pdf.close()

    with pytest.raises(OllamaServiceException) as exc:
        OcrService.preprocess_document_to_pages(pdf_path, ".pdf")

    assert exc.value.code == "PAGE_COUNT_EXCEEDED"
