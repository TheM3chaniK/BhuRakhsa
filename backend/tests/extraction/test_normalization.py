import pytest

from app.services.extraction_service import ExtractionService


def test_date_normalization() -> None:
    """Verify conservative date normalization into ISO YYYY-MM-DD."""
    assert (
        ExtractionService.normalize_field_value("registration_date", "12/03/2025")
        == "2025-03-12"
    )
    assert (
        ExtractionService.normalize_field_value("document_date", "05-11-2024")
        == "2024-11-05"
    )
    assert (
        ExtractionService.normalize_field_value("document_date", "2026-08-27")
        == "2026-08-27"
    )
    # Ambiguous or non-matching date preserved as trimmed string
    assert (
        ExtractionService.normalize_field_value("document_date", "Circa 1995")
        == "Circa 1995"
    )


def test_area_normalization() -> None:
    """Verify numeric component extraction for property area."""
    assert (
        ExtractionService.normalize_field_value("property_area", "2.50 Acres")
        == "2.50"
    )
    assert (
        ExtractionService.normalize_field_value("land_area", "1200 sq ft")
        == "1200"
    )
    assert (
        ExtractionService.normalize_field_value("property_area", "0.75 hectare")
        == "0.75"
    )


def test_string_name_normalization() -> None:
    """Verify whitespace collapsing and case-folding."""
    assert (
        ExtractionService.normalize_field_value("owner_name", "  RAMESH   KUMAR  ")
        == "ramesh kumar"
    )
    assert (
        ExtractionService.normalize_field_value("village", "  SHANTI NAGAR  ")
        == "shanti nagar"
    )
    assert ExtractionService.normalize_field_value("owner_name", None) is None
    assert ExtractionService.normalize_field_value("owner_name", "") is None
