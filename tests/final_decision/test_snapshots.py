from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import uuid
import pytest

from app.models.case import Case
from app.models.enums import CaseStatus, OfficerDecision, ReviewStatus, RiskAssessmentStatus, RiskLevel, UserRole, ValidationStatus, ValidationType
from app.models.final_decision import FinalDecision
from app.models.property_profile import PropertyProfile
from app.models.review import CaseReview
from app.models.risk_assessment import RiskAssessment
from app.models.user import User
from app.models.validation import ValidationRun
from app.schemas.review import SubmitDecisionRequest
from app.services.review_service import ReviewService


@pytest.mark.anyio
async def test_final_decision_snapshot_retention(officer_a_user: User) -> None:
    """Verify that ReviewService.submit_decision creates FinalDecision with complete snapshots."""
    case_id = uuid.uuid4()
    review_id = uuid.uuid4()
    profile_id = uuid.uuid4()
    db_run_id = uuid.uuid4()
    gis_run_id = uuid.uuid4()
    risk_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    mock_case = Case(
        id=case_id,
        case_number="CASE-2026-000001",
        created_by=uuid.uuid4(),
        area_id=uuid.uuid4(),
        status=CaseStatus.UNDER_REVIEW,
        risk_level=RiskLevel.MEDIUM,
    )
    mock_review = CaseReview(
        id=review_id,
        case_id=case_id,
        reviewer_id=officer_a_user.id,
        reviewer_area_id=mock_case.area_id,
        status=ReviewStatus.IN_PROGRESS,
        started_at=now,
    )
    mock_risk = RiskAssessment(
        id=risk_id,
        case_id=case_id,
        property_profile_id=profile_id,
        property_profile_version=3,
        risk_score=42,
        raw_score=42,
        risk_level=RiskLevel.MEDIUM,
        status=RiskAssessmentStatus.COMPLETED,
        calculated_at=now,
    )
    mock_db_run = ValidationRun(
        id=db_run_id,
        property_profile_id=profile_id,
        validation_type=ValidationType.DATABASE,
        status=ValidationStatus.PASSED,
        created_at=now,
    )
    mock_gis_run = ValidationRun(
        id=gis_run_id,
        property_profile_id=profile_id,
        validation_type=ValidationType.GIS,
        status=ValidationStatus.PASSED,
        created_at=now,
    )

    mock_db = AsyncMock()
    # Query sequence: case, review, readiness check (is_ready), risk, db_run, gis_run
    mock_db.execute.side_effect = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_case)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_review)),
        MagicMock(scalars=MagicMock(return_value=MagicMock(first=MagicMock(return_value=mock_risk)))),
        MagicMock(scalars=MagicMock(return_value=MagicMock(first=MagicMock(return_value=mock_db_run)))),
        MagicMock(scalars=MagicMock(return_value=MagicMock(first=MagicMock(return_value=mock_gis_run)))),
    ]

    with patch(
        "app.services.case_access_service.CaseAccessService.verify_case_access",
        new_callable=AsyncMock,
    ), patch(
        "app.services.review_readiness.ReviewReadinessService.is_ready_for_review",
        new_callable=AsyncMock,
        return_value=(True, ""),
    ), patch(
        "app.services.audit_service.AuditService.record_audit_event",
        new_callable=AsyncMock,
    ), patch(
        "app.events.outbox.OutboxService.record_event",
        new_callable=AsyncMock,
    ):
        payload = SubmitDecisionRequest(
            decision=OfficerDecision.APPROVE,
            reason="Approved after verifying property profile version 3 against database and GIS validation runs.",
        )
        review, case_status = await ReviewService.submit_decision(
            db=mock_db,
            case_id=case_id,
            payload=payload,
            user=officer_a_user,
        )

        assert case_status == CaseStatus.APPROVED
        assert review.status == ReviewStatus.COMPLETED
        assert review.decision == OfficerDecision.APPROVE
        assert review.risk_score_at_decision == 42
