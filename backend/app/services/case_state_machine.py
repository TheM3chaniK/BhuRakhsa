from typing import Optional, Set
import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.models.case import Case
from app.models.enums import AuditAction, AuditActorType, CaseStatus
from app.services.audit_service import AuditService


class CaseStateMachine:
    """Centralized state machine enforcing deterministic and valid case lifecycle transitions."""

    # Allowed forward transitions map
    ALLOWED_TRANSITIONS: dict[CaseStatus, Set[CaseStatus]] = {
        CaseStatus.DRAFT: {CaseStatus.SUBMITTED},
        CaseStatus.SUBMITTED: {CaseStatus.PROCESSING},
        CaseStatus.PROCESSING: {CaseStatus.REVIEW_READY, CaseStatus.SUBMITTED},
        CaseStatus.REVIEW_READY: {CaseStatus.UNDER_REVIEW},
        CaseStatus.UNDER_REVIEW: {
            CaseStatus.APPROVED,
            CaseStatus.REJECTED,
            CaseStatus.PROOF_REQUIRED,
            CaseStatus.REVIEW_READY,
        },
        CaseStatus.PROOF_REQUIRED: {
            CaseStatus.REVIEW_READY,
            CaseStatus.UNDER_REVIEW,
        },
        # Terminal states have no outgoing transitions
        CaseStatus.APPROVED: set(),
        CaseStatus.REJECTED: set(),
    }

    TERMINAL_STATES: Set[CaseStatus] = {CaseStatus.APPROVED, CaseStatus.REJECTED}

    @classmethod
    def can_transition(cls, current_status: CaseStatus, target_status: CaseStatus) -> bool:
        """Check if a transition from current_status to target_status is valid."""
        if current_status in cls.TERMINAL_STATES:
            return False
        return target_status in cls.ALLOWED_TRANSITIONS.get(current_status, set())

    @classmethod
    async def transition(
        cls,
        db: AsyncSession,
        case: Case,
        target_status: CaseStatus,
        actor_id: Optional[uuid.UUID] = None,
        actor_type: AuditActorType = AuditActorType.USER,
        reason: Optional[str] = None,
    ) -> Case:
        """Execute a validated case state transition and record an audit event atomically."""
        old_status = case.status

        if old_status in cls.TERMINAL_STATES:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Case is in a finalized terminal state ({old_status.value}) and cannot be transitioned.",
            )

        if not cls.can_transition(old_status, target_status):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Illegal state transition from '{old_status.value}' to '{target_status.value}'.",
            )

        case.status = target_status
        await db.flush()

        logger.info(
            "Case %s transitioned: %s -> %s by %s (%s)",
            case.id,
            old_status.value,
            target_status.value,
            actor_id,
            actor_type.value,
        )

        # Audit recording
        action_map = {
            CaseStatus.SUBMITTED: AuditAction.CASE_SUBMITTED,
            CaseStatus.APPROVED: AuditAction.FINAL_DECISION_CREATED,
            CaseStatus.REJECTED: AuditAction.FINAL_DECISION_CREATED,
            CaseStatus.UNDER_REVIEW: AuditAction.REVIEW_STARTED,
            CaseStatus.PROOF_REQUIRED: AuditAction.PROOF_REQUEST_CREATED,
            CaseStatus.REVIEW_READY: AuditAction.VALIDATION_COMPLETED,
            CaseStatus.PROCESSING: AuditAction.OCR_STARTED,
        }
        action = action_map.get(target_status, AuditAction.CASE_SUBMITTED)

        await AuditService.record_audit_event(
            db=db,
            action=action,
            case_id=case.id,
            actor_id=actor_id,
            actor_type=actor_type,
            entity_type="case",
            entity_id=case.id,
            old_state=old_status.value,
            new_state=target_status.value,
            metadata_json={"reason": reason} if reason else None,
        )

        return case
