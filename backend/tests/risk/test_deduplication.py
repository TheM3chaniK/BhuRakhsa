from datetime import datetime, timezone
import uuid
import pytest

from app.models.enums import MatchStatus, MismatchReason, MismatchSeverity, MismatchType, RiskLevel, ValidationType
from app.models.mismatch import Mismatch
from app.models.risk_factor import RiskFactor
from app.models.validation import ValidationRun
from app.models.validation_result import ValidationResult
from app.services.risk.mismatch_engine import MismatchEngine
from app.services.risk.risk_rules import RiskRules


def test_mismatch_and_factor_deduplication() -> None:
    """Verify identical discrepancies across multiple runs are deduplicated in risk factors."""
    case_id = uuid.uuid4()
    profile_id = uuid.uuid4()
    run_1_id = uuid.uuid4()
    run_2_id = uuid.uuid4()

    run_1 = ValidationRun(id=run_1_id, property_profile_id=profile_id, validation_type=ValidationType.DATABASE)
    run_1.results = [
        ValidationResult(
            id=uuid.uuid4(),
            validation_run_id=run_1_id,
            field_name="survey_number",
            match_status=MatchStatus.MISMATCH,
            mismatch_reason=MismatchReason.SURVEY_NUMBER_MISMATCH.value,
            document_value="123/45",
            reference_value="123/54",
        )
    ]

    run_2 = ValidationRun(id=run_2_id, property_profile_id=profile_id, validation_type=ValidationType.DATABASE)
    run_2.results = [
        ValidationResult(
            id=uuid.uuid4(),
            validation_run_id=run_2_id,
            field_name="survey_number",
            match_status=MatchStatus.MISMATCH,
            mismatch_reason=MismatchReason.SURVEY_NUMBER_MISMATCH.value,
            document_value="123/45",
            reference_value="123/54",
        )
    ]

    mismatches_1 = MismatchEngine.generate_from_validation_results(case_id, profile_id, run_1, {}, {})
    mismatches_2 = MismatchEngine.generate_from_validation_results(case_id, profile_id, run_2, {}, {})
    all_mismatches = mismatches_1 + mismatches_2
    assert len(all_mismatches) == 2

    # Deduplication logic test
    seen_factors = set()
    factors_to_create = []
    raw_score = 0

    for m in all_mismatches:
        dedup_key = (m.mismatch_type, m.field_name)
        if dedup_key in seen_factors:
            continue
        seen_factors.add(dedup_key)
        points = RiskRules.get_points(m.mismatch_type)
        raw_score += points
        factors_to_create.append(
            RiskFactor(
                id=uuid.uuid4(),
                factor_code=m.mismatch_type.value.upper(),
                severity=m.severity,
                points=points,
                description=m.description,
            )
        )

    assert len(factors_to_create) == 1
    assert raw_score == 30
