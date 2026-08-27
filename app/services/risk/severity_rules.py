from typing import Dict

from app.models.enums import MismatchSeverity, MismatchType

SEVERITY_RULE_VERSION = "1.0"


class SeverityRules:
    """Configurable severity mapping for validation discrepancies."""

    DEFAULT_SEVERITY_MAP: Dict[MismatchType, MismatchSeverity] = {
        # Ownership & Legal Identity
        MismatchType.OWNER_MISMATCH: MismatchSeverity.HIGH,
        MismatchType.PARCEL_NUMBER_MISMATCH: MismatchSeverity.CRITICAL,
        MismatchType.SURVEY_NUMBER_MISMATCH: MismatchSeverity.HIGH,
        MismatchType.PLOT_NUMBER_MISMATCH: MismatchSeverity.HIGH,
        MismatchType.REGISTRATION_NUMBER_MISMATCH: MismatchSeverity.HIGH,
        MismatchType.DEED_NUMBER_MISMATCH: MismatchSeverity.HIGH,
        # Surface Area
        MismatchType.AREA_MISMATCH: MismatchSeverity.MEDIUM,
        MismatchType.REFERENCE_GIS_AREA_MISMATCH: MismatchSeverity.MEDIUM,
        MismatchType.DOCUMENT_GIS_AREA_MISMATCH: MismatchSeverity.MEDIUM,
        # Administrative Location
        MismatchType.DISTRICT_MISMATCH: MismatchSeverity.MEDIUM,
        MismatchType.SUBDIVISION_MISMATCH: MismatchSeverity.MEDIUM,
        MismatchType.VILLAGE_MISMATCH: MismatchSeverity.LOW,
        MismatchType.MOUZA_MISMATCH: MismatchSeverity.LOW,
        MismatchType.WARD_MISMATCH: MismatchSeverity.LOW,
        # Spatial / GIS
        MismatchType.PARCEL_NOT_FOUND: MismatchSeverity.HIGH,
        MismatchType.PARCEL_GEOMETRY_NOT_FOUND: MismatchSeverity.MEDIUM,
        MismatchType.INVALID_PARCEL_GEOMETRY: MismatchSeverity.HIGH,
        MismatchType.POINT_OUTSIDE_PARCEL: MismatchSeverity.HIGH,
        MismatchType.DISTRICT_LOCATION_MISMATCH: MismatchSeverity.HIGH,
        MismatchType.VILLAGE_LOCATION_MISMATCH: MismatchSeverity.MEDIUM,
        # Extraction & Ambiguity
        MismatchType.MULTIPLE_REFERENCE_CANDIDATES: MismatchSeverity.MEDIUM,
        MismatchType.EXTRACTION_CONFLICT: MismatchSeverity.MEDIUM,
    }

    @classmethod
    def get_severity(cls, mismatch_type: MismatchType) -> MismatchSeverity:
        """Resolve severity tier for discrepancy type."""
        return cls.DEFAULT_SEVERITY_MAP.get(mismatch_type, MismatchSeverity.MEDIUM)
