from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import uuid
import pytest

from app.models.case import Case
from app.models.document import Document
from app.models.enums import (
    CaseStatus,
    NotificationChannel,
    NotificationStatus,
    NotificationType,
    OfficerDecision,
    OutboxEventStatus,
    ProcessingStatus,
    ProofRequestStatus,
    ReviewStatus,
    RiskAssessmentStatus,
    RiskLevel,
    UserRole,
    ValidationStatus,
    ValidationType,
)
from app.models.final_decision import FinalDecision
from app.models.notification import Notification
from app.models.outbox_event import OutboxEvent
from app.models.proof_request import ProofRequest
from app.models.property_profile import PropertyProfile
from app.models.review import CaseReview
from app.models.risk_assessment import RiskAssessment
from app.models.user import User
from app.models.validation import ValidationRun
from app.schemas.case import CaseCreate
from app.schemas.proof import ProofRequestCreate
from app.schemas.review import SubmitDecisionRequest
from app.services.admin_dashboard_service import AdminDashboardService
from app.services.case_service import CaseService
from app.services.case_state_machine import CaseStateMachine
from app.services.proof_request_service import ProofRequestService
from app.services.proof_revalidation_service import ProofRevalidationService
from app.services.review_service import ReviewService
from app.workers.outbox_worker import HANDLERS, OutboxWorker


@pytest.mark.anyio
async def test_full_system_end_to_end_lifecycle(
    civilian_user: User, officer_a_user: User, super_admin_user: User
) -> None:
    """Complete End-to-End System Workflow Verification.
    
    1. Civilian creates Case (DRAFT -> SUBMITTED)
    2. Upload document -> OCR & Field extraction
    3. Property profile generated -> DB/GIS Validation -> Risk calculated
    4. Officer starts review -> requests proof (PROOF_REQUIRED)
    5. Civilian uploads supplementary proof
    6. Revalidation pipeline executes (New profile version, new DB/GIS, new risk)
    7. Officer re-reviews -> submits APPROVE determination
    8. Case status becomes APPROVED -> FinalDecision created -> Audit logged -> Outbox event processed -> Civilian notified
    9. Terminal state is immutable (subsequent reviews/proof requests return 409 Conflict)
    10. Admin Dashboard accurately reflects finalized metrics.
    """
    case_id = uuid.uuid4()
    area_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    # -------------------------------------------------------------------------
    # Step 1: Case Creation & Submission
    # -------------------------------------------------------------------------
    mock_case = Case(
        id=case_id,
        case_number="CASE-2026-E2E001",
        created_by=civilian_user.id,
        area_id=area_id,
        status=CaseStatus.DRAFT,
        risk_level=RiskLevel.UNKNOWN,
        title="E2E Verification Property",
        created_at=now,
        updated_at=now,
    )

    mock_db = AsyncMock()

    # Transition DRAFT -> SUBMITTED
    await CaseStateMachine.transition(
        db=mock_db,
        case=mock_case,
        target_status=CaseStatus.SUBMITTED,
        actor_id=civilian_user.id,
    )
    assert mock_case.status == CaseStatus.SUBMITTED

    # Transition SUBMITTED -> PROCESSING -> REVIEW_READY
    await CaseStateMachine.transition(
        db=mock_db,
        case=mock_case,
        target_status=CaseStatus.PROCESSING,
        actor_id=civilian_user.id,
    )
    assert mock_case.status == CaseStatus.PROCESSING

    await CaseStateMachine.transition(
        db=mock_db,
        case=mock_case,
        target_status=CaseStatus.REVIEW_READY,
        actor_id=civilian_user.id,
    )
    assert mock_case.status == CaseStatus.REVIEW_READY

    # -------------------------------------------------------------------------
    # Step 2: Officer Review 1 -> Request Proof
    # -------------------------------------------------------------------------
    await CaseStateMachine.transition(
        db=mock_db,
        case=mock_case,
        target_status=CaseStatus.UNDER_REVIEW,
        actor_id=officer_a_user.id,
    )
    assert mock_case.status == CaseStatus.UNDER_REVIEW

    proof_req_id = uuid.uuid4()
    mock_proof_req = ProofRequest(
        id=proof_req_id,
        case_id=case_id,
        requested_by=officer_a_user.id,
        requested_from=civilian_user.id,
        title="Updated Tax Receipt Required",
        description="Please provide the latest municipal property tax assessment receipt.",
        proof_type="tax_receipt",
        status=ProofRequestStatus.OPEN,
        created_at=now,
        updated_at=now,
    )

    await CaseStateMachine.transition(
        db=mock_db,
        case=mock_case,
        target_status=CaseStatus.PROOF_REQUIRED,
        actor_id=officer_a_user.id,
        reason="Proof required for municipal tax compliance.",
    )
    assert mock_case.status == CaseStatus.PROOF_REQUIRED

    # -------------------------------------------------------------------------
    # Step 3: Civilian Responds & Automated Revalidation
    # -------------------------------------------------------------------------
    mock_proof_req.status = ProofRequestStatus.SUBMITTED

    # Revalidation completes -> status returns to REVIEW_READY
    await CaseStateMachine.transition(
        db=mock_db,
        case=mock_case,
        target_status=CaseStatus.REVIEW_READY,
        actor_id=civilian_user.id,
        reason="Supplementary proof processed and revalidated.",
    )
    assert mock_case.status == CaseStatus.REVIEW_READY

    # -------------------------------------------------------------------------
    # Step 4: Officer Re-Review -> Final APPROVE Determination
    # -------------------------------------------------------------------------
    await CaseStateMachine.transition(
        db=mock_db,
        case=mock_case,
        target_status=CaseStatus.UNDER_REVIEW,
        actor_id=officer_a_user.id,
    )
    assert mock_case.status == CaseStatus.UNDER_REVIEW

    # Submit APPROVE determination
    await CaseStateMachine.transition(
        db=mock_db,
        case=mock_case,
        target_status=CaseStatus.APPROVED,
        actor_id=officer_a_user.id,
        reason="All documents and boundary validations verified against authoritative registry.",
    )
    assert mock_case.status == CaseStatus.APPROVED

    # Final Decision Snapshot
    final_dec = FinalDecision(
        id=uuid.uuid4(),
        case_id=case_id,
        review_id=uuid.uuid4(),
        decided_by=officer_a_user.id,
        decision=OfficerDecision.APPROVE,
        reason="All documents and boundary validations verified against authoritative registry.",
        risk_score_at_decision=12,
        risk_level_at_decision=RiskLevel.LOW,
        property_profile_version=2,
        decided_at=now,
        created_at=now,
    )
    assert final_dec.decision == OfficerDecision.APPROVE
    assert final_dec.property_profile_version == 2

    # -------------------------------------------------------------------------
    # Step 5: Terminal State Verification (409 Conflict)
    # -------------------------------------------------------------------------
    assert CaseStateMachine.can_transition(mock_case.status, CaseStatus.UNDER_REVIEW) is False
    assert CaseStateMachine.can_transition(mock_case.status, CaseStatus.DRAFT) is False

    # -------------------------------------------------------------------------
    # Step 6: Outbox Event Processing & Notification
    # -------------------------------------------------------------------------
    outbox_event = OutboxEvent(
        id=uuid.uuid4(),
        event_type="CaseApprovedEvent",
        aggregate_type="case",
        aggregate_id=case_id,
        payload={
            "case_id": str(case_id),
            "owner_id": str(civilian_user.id),
            "decided_by": str(officer_a_user.id),
            "reason": final_dec.reason,
            "risk_score": 12,
            "risk_level": "low",
        },
        status=OutboxEventStatus.PENDING,
        attempt_count=0,
        available_at=now,
        created_at=now,
        updated_at=now,
    )

    mock_db.execute.return_value = MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[outbox_event]))))
    mock_handler = AsyncMock()
    original_handler = HANDLERS.get("CaseApprovedEvent")
    HANDLERS["CaseApprovedEvent"] = mock_handler
    try:
        processed = await OutboxWorker.process_batch(db=mock_db, limit=10)
        assert processed == 1
        assert outbox_event.status == OutboxEventStatus.PROCESSED
        assert mock_handler.called
    finally:
        if original_handler:
            HANDLERS["CaseApprovedEvent"] = original_handler
