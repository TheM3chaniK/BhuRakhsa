import uuid
import pytest

from app.models.enums import MatchStatus, MismatchReason, MismatchSeverity, MismatchSource, MismatchType, ValidationType
from app.models.property_field_conflict import PropertyFieldConflict
from app.models.validation import ValidationRun
from app.models.validation_result import ValidationResult
from app.services.risk.mismatch_engine import MismatchEngine


def test_mismatch_engine_filters_matches_and_builds_discrepancies() -> None:
    """Verify MismatchEngine filters MATCH and generates Mismatch records for discrepancies with evidence links."""
    case_id = uuid.uuid4()
    profile_id = uuid.uuid4()
    run_id = uuid.uuid4()
    ext_field_id = uuid.uuid4()
    evidence_id = uuid.uuid4()

    val_run = ValidationRun(
        id=run_id,
        property_profile_id=profile_id,
        validation_type=ValidationType.DATABASE,
    )
    val_run.results = [
        # Match - Should not produce a Mismatch
        ValidationResult(
            id=uuid.uuid4(),
            validation_run_id=run_id,
            field_name="owner_name",
            match_status=MatchStatus.MATCH,
            document_value="Rajesh Kumar Sharma",
            reference_value="Rajesh Kumar Sharma",
        ),
        # Mismatch - Should produce a Mismatch
        ValidationResult(
            id=uuid.uuid4(),
            validation_run_id=run_id,
            field_name="survey_number",
            match_status=MatchStatus.MISMATCH,
            mismatch_reason=MismatchReason.SURVEY_NUMBER_MISMATCH.value,
            document_value="123/45",
            reference_value="123/54",
        ),
    ]

    field_source_map = {"survey_number": ext_field_id}
    extracted_field_evidence_map = {ext_field_id: evidence_id}

    mismatches = MismatchEngine.generate_from_validation_results(
        case_id=case_id,
        profile_id=profile_id,
        val_run=val_run,
        field_source_map=field_source_map,
        extracted_field_evidence_map=extracted_field_evidence_map,
    )

    assert len(mismatches) == 1
    m = mismatches[0]
    assert m.mismatch_type == MismatchType.SURVEY_NUMBER_MISMATCH
    assert m.mismatch_source == MismatchSource.DATABASE
    assert m.severity == MismatchSeverity.HIGH
    assert m.document_value == "123/45"
    assert m.reference_value == "123/54"
    assert "123/45" in m.description and "123/54" in m.description

    # Traceability
    assert len(m.evidence_links) == 1
    link = m.evidence_links[0]
    assert link.extracted_field_id == ext_field_id
    assert link.evidence_id == evidence_id
    assert link.validation_result_id == val_run.results[1].id


def test_mismatch_engine_handles_extraction_conflicts() -> None:
    """Verify multi-document extraction conflicts produce EXTRACTION_CONFLICT mismatches."""
    case_id = uuid.uuid4()
    profile_id = uuid.uuid4()
    ext_field_id = uuid.uuid4()
    evidence_id = uuid.uuid4()

    conflict = PropertyFieldConflict(
        id=uuid.uuid4(),
        property_profile_id=profile_id,
        field_name="survey_number",
        value_a="123/45",
        value_b="123/54",
        source_a="Doc A",
        source_b="Doc B",
    )

    field_source_map = {"survey_number": ext_field_id}
    extracted_field_evidence_map = {ext_field_id: evidence_id}

    mismatches = MismatchEngine.generate_from_extraction_conflicts(
        case_id=case_id,
        profile_id=profile_id,
        conflicts=[conflict],
        field_source_map=field_source_map,
        extracted_field_evidence_map=extracted_field_evidence_map,
    )

    assert len(mismatches) == 1
    m = mismatches[0]
    assert m.mismatch_type == MismatchType.EXTRACTION_CONFLICT
    assert m.mismatch_source == MismatchSource.EXTRACTION
    assert m.severity == MismatchSeverity.MEDIUM
    assert "Conflicting values detected" in m.description
