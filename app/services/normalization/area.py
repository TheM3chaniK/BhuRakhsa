from typing import Optional, Tuple


class AreaNormalizer:
    """Unit conversion and tolerance evaluation for property surface measurements."""

    # Standard conversion factors to Square Meters
    UNIT_TO_SQ_METERS = {
        "sqm": 1.0,
        "sq_meter": 1.0,
        "sq_meters": 1.0,
        "square_meter": 1.0,
        "square_meters": 1.0,
        "sq m": 1.0,
        "m2": 1.0,
        "acre": 4046.8564224,
        "acres": 4046.8564224,
        "ac": 4046.8564224,
        "hectare": 10000.0,
        "hectares": 10000.0,
        "ha": 10000.0,
        "sqft": 0.092903,
        "sq_feet": 0.092903,
        "sq_foot": 0.092903,
        "square_feet": 0.092903,
        "square_foot": 0.092903,
        "sq ft": 0.092903,
        "sq. ft.": 0.092903,
        "guntha": 101.17,
        "gunthas": 101.17,
        "guntas": 101.17,
    }

    @classmethod
    def normalize_unit(cls, unit: Optional[str]) -> Optional[str]:
        """Clean and standardize unit label."""
        if not unit or not unit.strip():
            return None
        clean = unit.strip().lower().replace(".", "").replace("-", "_")
        return clean

    @classmethod
    def to_square_meters(
        cls, value: Optional[float], unit: Optional[str]
    ) -> Optional[float]:
        """Convert a given area extent to standard square meters."""
        if value is None or value < 0:
            return None

        clean_unit = cls.normalize_unit(unit)
        if not clean_unit:
            return None

        # Check standard dictionary
        for u_key, factor in cls.UNIT_TO_SQ_METERS.items():
            if clean_unit == u_key or clean_unit.replace(" ", "") == u_key.replace(" ", ""):
                return value * factor

        return None

    @classmethod
    def compare_areas(
        cls,
        val_doc: Optional[float],
        unit_doc: Optional[str],
        val_ref: Optional[float],
        unit_ref: Optional[str],
        tolerance_percent: float = 1.0,
    ) -> Tuple[bool, Optional[float], Optional[str]]:
        """Compare document area and reference area within a configured percentage tolerance.
        
        Returns: (is_match, similarity_score, error_reason)
        """
        if val_doc is None or val_ref is None:
            return False, 0.0, "MISSING_VALUE"

        sqm_doc = cls.to_square_meters(val_doc, unit_doc)
        sqm_ref = cls.to_square_meters(val_ref, unit_ref)

        if sqm_doc is None or sqm_ref is None:
            return False, 0.0, "UNSUPPORTED_UNIT"

        if sqm_ref == 0.0:
            match = sqm_doc == 0.0
            return match, 1.0 if match else 0.0, None if match else "AREA_MISMATCH"

        percent_diff = abs(sqm_doc - sqm_ref) / sqm_ref * 100.0
        similarity = max(0.0, min(1.0, 1.0 - (percent_diff / 100.0)))

        if percent_diff <= tolerance_percent:
            return True, similarity, None

        return False, similarity, "AREA_MISMATCH"
