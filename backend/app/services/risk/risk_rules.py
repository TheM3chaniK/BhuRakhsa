from typing import Dict

from app.models.enums import MismatchType, RiskLevel

RISK_RULE_VERSION = "1.0"


class RiskRules:
    """Deterministic, configurable risk scoring point allocations and classification thresholds."""

    DEFAULT_POINT_MAP: Dict[MismatchType, int] = {
        # Ownership & Legal Identity
        MismatchType.PARCEL_NUMBER_MISMATCH: 40,
        MismatchType.SURVEY_NUMBER_MISMATCH: 30,
        MismatchType.REGISTRATION_NUMBER_MISMATCH: 30,
        MismatchType.OWNER_MISMATCH: 25,
        MismatchType.PLOT_NUMBER_MISMATCH: 25,
        MismatchType.DEED_NUMBER_MISMATCH: 25,
        # Surface Area
        MismatchType.AREA_MISMATCH: 15,
        MismatchType.REFERENCE_GIS_AREA_MISMATCH: 15,
        MismatchType.DOCUMENT_GIS_AREA_MISMATCH: 15,
        # Spatial / GIS
        MismatchType.PARCEL_NOT_FOUND: 35,
        MismatchType.POINT_OUTSIDE_PARCEL: 30,
        MismatchType.DISTRICT_LOCATION_MISMATCH: 20,
        MismatchType.INVALID_PARCEL_GEOMETRY: 20,
        MismatchType.VILLAGE_LOCATION_MISMATCH: 10,
        MismatchType.PARCEL_GEOMETRY_NOT_FOUND: 10,
        # Administrative Location
        MismatchType.DISTRICT_MISMATCH: 15,
        MismatchType.SUBDIVISION_MISMATCH: 10,
        MismatchType.VILLAGE_MISMATCH: 5,
        MismatchType.MOUZA_MISMATCH: 5,
        MismatchType.WARD_MISMATCH: 5,
        # Conflicts & Ambiguity
        MismatchType.EXTRACTION_CONFLICT: 15,
        MismatchType.MULTIPLE_REFERENCE_CANDIDATES: 10,
    }

    @classmethod
    def get_points(cls, mismatch_type: MismatchType) -> int:
        """Resolve risk point contribution for discrepancy type."""
        return cls.DEFAULT_POINT_MAP.get(mismatch_type, 10)

    @classmethod
    def get_risk_level(cls, score: int) -> RiskLevel:
        """Map integer risk score (0-100) to review priority tier."""
        if score >= 80:
            return RiskLevel.CRITICAL
        elif score >= 50:
            return RiskLevel.HIGH
        elif score >= 20:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW
