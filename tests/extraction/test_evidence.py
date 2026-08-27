import pytest

from app.services.extraction_service import ExtractionService


def test_evidence_grounding_verification() -> None:
    """Verify source_text grounding in OCR page text and rejection of hallucinated citations."""
    ocr_page_1 = """
    GOVERNMENT OF MAHARASHTRA
    TITLE DEED REGISTRATION
    Owner Name: Ramesh Kumar
    Survey Number: 123/45
    Extent: 2.50 Acres
    Village: Shanti Nagar
    """

    # 1. Exact & normalized matches -> True
    assert (
        ExtractionService.verify_source_text_grounding(
            ocr_page_text=ocr_page_1,
            source_text="Owner Name: Ramesh Kumar",
        )
        is True
    )
    assert (
        ExtractionService.verify_source_text_grounding(
            ocr_page_text=ocr_page_1,
            source_text="survey number: 123/45",
        )
        is True
    )
    assert (
        ExtractionService.verify_source_text_grounding(
            ocr_page_text=ocr_page_1,
            source_text="Extent: 2.50 Acres",
        )
        is True
    )

    # 2. Hallucinated / modified source text -> False
    assert (
        ExtractionService.verify_source_text_grounding(
            ocr_page_text=ocr_page_1,
            source_text="Owner: Suresh Sharma",
        )
        is False
    )
    assert (
        ExtractionService.verify_source_text_grounding(
            ocr_page_text=ocr_page_1,
            source_text="Plot No 999",
        )
        is False
    )
    assert (
        ExtractionService.verify_source_text_grounding(
            ocr_page_text=ocr_page_1,
            source_text="",
        )
        is False
    )
