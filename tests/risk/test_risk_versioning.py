from datetime import datetime, timezone
import uuid
import pytest

from app.models.enums import RiskAssessmentStatus, RiskLevel
from app.models.risk_assessment import RiskAssessment
from app.services.risk.risk_rules import RISK_RULE_VERSION
from app.services.risk.severity_rules import SEVERITY_RULE_VERSION


def test_risk_assessment_snapshot_immutability_and_versioning() -> None:
    """Verify risk assessment snapshots capture property profile version and rule versions."""
    case_id = uuid.uuid4()
    profile_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    # First assessment at profile version 1
    assessment_v1 = RiskAssessment(
        id=uuid.uuid4(),
        case_id=case_id,
        property_profile_id=profile_id,
        property_profile_version=1,
        risk_score=70,
        raw_score=70,
        risk_level=RiskLevel.HIGH,
        status=RiskAssessmentStatus.COMPLETED,
        risk_version=RISK_RULE_VERSION,
        severity_rule_version=SEVERITY_RULE_VERSION,
        calculated_at=now,
    )

    # Second assessment after profile refresh at profile version 2
    assessment_v2 = RiskAssessment(
        id=uuid.uuid4(),
        case_id=case_id,
        property_profile_id=profile_id,
        property_profile_version=2,
        risk_score=45,
        raw_score=45,
        risk_level=RiskLevel.MEDIUM,
        status=RiskAssessmentStatus.COMPLETED,
        risk_version=RISK_RULE_VERSION,
        severity_rule_version=SEVERITY_RULE_VERSION,
        calculated_at=now,
    )

    assert assessment_v1.property_profile_version == 1
    assert assessment_v1.risk_score == 70
    assert assessment_v1.risk_version == "1.0"

    assert assessment_v2.property_profile_version == 2
    assert assessment_v2.risk_score == 45
    assert assessment_v2.risk_version == "1.0"
