import pytest

from app.services.normalization.area import AreaNormalizer
from app.services.normalization.identifier import IdentifierNormalizer
from app.services.normalization.name import NameNormalizer


def test_identifier_normalizer() -> None:
    """Verify conservative identifier normalization."""
    assert IdentifierNormalizer.normalize(" 123 / 45 ") == "123/45"
    assert IdentifierNormalizer.normalize(" P - 001 ") == "p-001"
    assert IdentifierNormalizer.normalize("REG . 2025 . 01") == "reg.2025.01"
    assert IdentifierNormalizer.normalize(None) is None
    assert IdentifierNormalizer.normalize("") is None


def test_name_normalizer() -> None:
    """Verify name cleaning and honorific stripping."""
    assert NameNormalizer.normalize(" Shri  Ramesh   Kumar ") == "ramesh kumar"
    assert NameNormalizer.normalize("Dr. Suresh Kumar") == "suresh kumar"
    assert NameNormalizer.normalize("Smt. Anita Late Sharma") == "anita sharma"
    assert NameNormalizer.normalize(None) is None


def test_area_normalizer_conversion_and_tolerance() -> None:
    """Verify area conversion to square meters and tolerance matching."""
    # 1. Conversion to square meters
    sqm_1_acre = AreaNormalizer.to_square_meters(1.0, "acre")
    assert sqm_1_acre is not None
    assert round(sqm_1_acre, 2) == 4046.86

    sqm_1_ha = AreaNormalizer.to_square_meters(1.0, "hectare")
    assert sqm_1_ha == 10000.0

    # 2. Equivalent area matching across units
    # 2.47105 acres ~ 1.0 hectare
    is_match, score, err = AreaNormalizer.compare_areas(
        val_doc=2.471,
        unit_doc="acres",
        val_ref=1.0,
        unit_ref="hectare",
        tolerance_percent=1.0,
    )
    assert is_match is True
    assert err is None

    # 3. Area within 1% tolerance
    is_match_tol, _, _ = AreaNormalizer.compare_areas(
        val_doc=2.50,
        unit_doc="acres",
        val_ref=2.51,
        unit_ref="acres",
        tolerance_percent=1.0,
    )
    assert is_match_tol is True

    # 4. Area beyond tolerance
    is_match_diff, _, err_diff = AreaNormalizer.compare_areas(
        val_doc=2.50,
        unit_doc="acres",
        val_ref=3.00,
        unit_ref="acres",
        tolerance_percent=1.0,
    )
    assert is_match_diff is False
    assert err_diff == "AREA_MISMATCH"
