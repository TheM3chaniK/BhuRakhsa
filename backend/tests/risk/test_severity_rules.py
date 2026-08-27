import pytest

from app.models.enums import MismatchSeverity, MismatchType
from app.services.risk.severity_rules import SEVERITY_RULE_VERSION, SeverityRules


def test_severity_rules_resolution_and_version() -> None:
    """Verify severity resolution maps critical and high discrepancies as configured."""
    assert SEVERITY_RULE_VERSION == "1.0"

    assert SeverityRules.get_severity(MismatchType.PARCEL_NUMBER_MISMATCH) == MismatchSeverity.CRITICAL
    assert SeverityRules.get_severity(MismatchType.OWNER_MISMATCH) == MismatchSeverity.HIGH
    assert SeverityRules.get_severity(MismatchType.SURVEY_NUMBER_MISMATCH) == MismatchSeverity.HIGH
    assert SeverityRules.get_severity(MismatchType.POINT_OUTSIDE_PARCEL) == MismatchSeverity.HIGH
    assert SeverityRules.get_severity(MismatchType.AREA_MISMATCH) == MismatchSeverity.MEDIUM
    assert SeverityRules.get_severity(MismatchType.VILLAGE_MISMATCH) == MismatchSeverity.LOW
    assert SeverityRules.get_severity(MismatchType.EXTRACTION_CONFLICT) == MismatchSeverity.MEDIUM
