from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
import uuid
import pytest

from app.models.case import Case
from app.models.enums import (
    CaseStatus,
    MatchStatus,
    MismatchReason,
    MismatchType,
    RiskLevel,
    ValidationType,
)
from app.models.property_profile import PropertyProfile
from app.models.risk_assessment import RiskAssessment
from app.models.validation import ValidationRun
from app.models.validation_result import ValidationResult
from app.services.risk.risk_engine import RiskEngine
from app.services.risk.risk_rules import RiskRules


def test_risk_rules_score_and_level_mapping() -> None:
    """Verify points allocations and risk level thresholds."""
    assert RiskRules.get_points(MismatchType.SURVEY_NUMBER_MISMATCH) == 30
    assert RiskRules.get_points(MismatchType.OWNER_MISMATCH) == 25
    assert RiskRules.get_points(MismatchType.POINT_OUTSIDE_PARCEL) == 30

    assert RiskRules.get_risk_level(0) == RiskLevel.LOW
    assert RiskRules.get_risk_level(15) == RiskLevel.LOW
    assert RiskRules.get_risk_level(20) == RiskLevel.MEDIUM
    assert RiskRules.get_risk_level(45) == RiskLevel.MEDIUM
    assert RiskRules.get_risk_level(50) == RiskLevel.HIGH
    assert RiskRules.get_risk_level(75) == RiskLevel.HIGH
    assert RiskRules.get_risk_level(80) == RiskLevel.CRITICAL
    assert RiskRules.get_risk_level(100) == RiskLevel.CRITICAL


@pytest.mark.anyio
async def test_risk_calculation_pipeline_multiple_mismatches() -> None:
    """Verify combined database and GIS mismatches yield correct deterministic score (85 -> CRITICAL)."""
    case_id = uuid.uuid4()
    profile_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    case = Case(
        id=case_id,
        case_number="CASE-2026-000001",
        created_by=uuid.uuid4(),
        area_id=uuid.uuid4(),
        status=CaseStatus.PROCESSING,
        risk_level=RiskLevel.UNKNOWN,
    )
    profile = PropertyProfile(
        id=profile_id,
        case_id=case_id,
        version=1,
    )
    profile.conflicts = []
    profile.field_sources = []

    # Database run with Survey mismatch (+30) and Owner mismatch (+25)
    db_run = ValidationRun(
        id=uuid.uuid4(),
        property_profile_id=profile_id,
        validation_type=ValidationType.DATABASE,
    )
    db_run.results = [
        ValidationResult(
            id=uuid.uuid4(),
            validation_run_id=db_run.id,
            field_name="survey_number",
            match_status=MatchStatus.MISMATCH,
            mismatch_reason=MismatchReason.SURVEY_NUMBER_MISMATCH.value,
            document_value="123/45",
            reference_value="123/54",
        ),
        ValidationResult(
            id=uuid.uuid4(),
            validation_run_id=db_run.id,
            field_name="owner_name",
            match_status=MatchStatus.MISMATCH,
            mismatch_reason=MismatchReason.OWNER_MISMATCH.value,
            document_value="Rajesh Sharma",
            reference_value="Suresh Sharma",
        ),
    ]

    # GIS run with Point outside parcel (+30)
    gis_run = ValidationRun(
        id=uuid.uuid4(),
        property_profile_id=profile_id,
        validation_type=ValidationType.GIS,
    )
    gis_run.results = [
        ValidationResult(
            id=uuid.uuid4(),
            validation_run_id=gis_run.id,
            field_name="point_inside_parcel",
            match_status=MatchStatus.MISMATCH,
            mismatch_reason=MismatchReason.POINT_OUTSIDE_PARCEL.value,
            document_value="POINT(73.0050 20.0050)",
            reference_value="Outside parcel boundary",
            geometry_distance_meters=153.4,
        ),
    ]

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()

    val_run_calls = 0

    async def mock_execute(stmt):
        nonlocal val_run_calls
        mock_result = MagicMock()
        stmt_str = str(stmt)
        if "FROM cases" in stmt_str:
            mock_result.scalar_one_or_none.return_value = case
        elif "FROM property_profiles" in stmt_str:
            mock_result.scalar_one_or_none.return_value = profile
        elif "FROM evidence" in stmt_str:
            mock_result.scalars.return_value.all.return_value = []
        elif "FROM validation_runs" in stmt_str:
            val_run_calls += 1
            if val_run_calls == 1:
                mock_result.scalars.return_value.first.return_value = db_run
            else:
                mock_result.scalars.return_value.first.return_value = gis_run
        elif "FROM risk_assessments" in stmt_str:
            assessment = RiskAssessment(
                id=uuid.uuid4(),
                case_id=case_id,
                property_profile_id=profile_id,
                property_profile_version=1,
                risk_score=85,
                raw_score=85,
                risk_level=RiskLevel.CRITICAL,
                calculated_at=now,
            )
            mock_result.scalar_one.return_value = assessment
        return mock_result

    mock_db.execute.side_effect = mock_execute

    assessment = await RiskEngine.calculate_case_risk(
        db=mock_db,
        case_id=case_id,
        user=None,
        require_jurisdiction=False,
    )

    assert assessment.risk_score == 85
    assert assessment.risk_level == RiskLevel.CRITICAL
    assert case.risk_level == RiskLevel.CRITICAL
