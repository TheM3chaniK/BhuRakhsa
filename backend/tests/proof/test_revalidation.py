from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import uuid
import pytest

from app.models.enums import ProofRequestStatus, ProofSubmissionStatus, ValidationStatus, ValidationType
from app.models.proof_request import ProofRequest
from app.models.proof_submission import ProofSubmission
from app.models.property_profile import PropertyProfile
from app.models.risk_assessment import RiskAssessment
from app.models.validation import ValidationRun
from app.services.proof_revalidation_service import ProofRevalidationService


@pytest.mark.anyio
async def test_revalidation_service_pipeline() -> None:
    """Verify proof revalidation refreshes profile, executes validations, and calculates updated risk."""
    case_id = uuid.uuid4()
    req_id = uuid.uuid4()
    sub_id = uuid.uuid4()
    profile_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    mock_req = ProofRequest(
        id=req_id,
        case_id=case_id,
        requested_by=uuid.uuid4(),
        requested_from=uuid.uuid4(),
        title="Title Clearance",
        description="Clearance doc",
        status=ProofRequestStatus.SUBMITTED,
        created_at=now,
        updated_at=now,
    )

    mock_sub = ProofSubmission(
        id=sub_id,
        proof_request_id=req_id,
        submitted_by=uuid.uuid4(),
        document_id=uuid.uuid4(),
        status=ProofSubmissionStatus.PROCESSING,
        submitted_at=now,
        created_at=now,
        updated_at=now,
    )

    mock_profile = PropertyProfile(
        id=profile_id,
        case_id=case_id,
        version=2,
        created_at=now,
        updated_at=now,
    )

    mock_db_run = ValidationRun(
        id=uuid.uuid4(),
        property_profile_id=profile_id,
        validation_type=ValidationType.DATABASE,
        status=ValidationStatus.PASSED,
    )

    mock_gis_run = ValidationRun(
        id=uuid.uuid4(),
        property_profile_id=profile_id,
        validation_type=ValidationType.GIS,
        status=ValidationStatus.PASSED,
    )

    mock_risk = RiskAssessment(
        id=uuid.uuid4(),
        case_id=case_id,
        property_profile_id=profile_id,
        property_profile_version=2,
        risk_score=10,
        raw_score=10,
        risk_level="low",
    )

    mock_db = AsyncMock()
    mock_result_sub = MagicMock()
    mock_result_sub.scalar_one_or_none.return_value = mock_sub

    mock_result_req = MagicMock()
    mock_result_req.scalar_one_or_none.return_value = mock_req

    mock_db.execute.side_effect = [mock_result_sub, mock_result_req]

    with patch(
        "app.services.property_profile_service.PropertyProfileService.generate_profile",
        new_callable=AsyncMock,
    ) as mock_gen_prof, patch(
        "app.services.property_profile_service.PropertyProfileService.create_validation_run",
        new_callable=AsyncMock,
    ) as mock_create_run, patch(
        "app.services.validation.database_validator.DatabaseValidator.validate_run",
        new_callable=AsyncMock,
    ) as mock_val_db, patch(
        "app.services.validation.gis_validator.GISValidator.validate_run",
        new_callable=AsyncMock,
    ) as mock_val_gis, patch(
        "app.services.risk.risk_engine.RiskEngine.calculate_case_risk",
        new_callable=AsyncMock,
    ) as mock_risk_calc:

        mock_gen_prof.return_value = (mock_profile, [])
        mock_create_run.side_effect = [mock_db_run, mock_gis_run]
        mock_val_db.return_value = (ValidationStatus.PASSED, [], [])
        mock_val_gis.return_value = (ValidationStatus.PASSED, [])
        mock_risk_calc.return_value = mock_risk

        success = await ProofRevalidationService.revalidate_case_after_proof(
            db=mock_db,
            case_id=case_id,
            proof_submission_id=sub_id,
        )

        assert success is True
        assert mock_sub.status == ProofSubmissionStatus.PROCESSED
        assert mock_gen_prof.called
        assert mock_val_db.called
        assert mock_val_gis.called
        assert mock_risk_calc.called
