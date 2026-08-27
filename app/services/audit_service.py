from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_event import AuditEvent
from app.models.case import Case
from app.models.enums import AuditAction, AuditActorType, UserRole
from app.models.user import User
from app.services.case_access_service import CaseAccessService


class AuditService:
    """Service writing immutable domain audit log records and querying role-filtered audit timelines."""

    CIVILIAN_SAFE_ACTIONS = {
        AuditAction.CASE_CREATED,
        AuditAction.CASE_SUBMITTED,
        AuditAction.DOCUMENT_UPLOADED,
        AuditAction.OCR_COMPLETED,
        AuditAction.EXTRACTION_COMPLETED,
        AuditAction.VALIDATION_COMPLETED,
        AuditAction.REVIEW_STARTED,
        AuditAction.PROOF_REQUEST_CREATED,
        AuditAction.PROOF_SUBMITTED,
        AuditAction.PROOF_ACCEPTED,
        AuditAction.PROOF_REJECTED,
        AuditAction.CASE_APPROVED,
        AuditAction.CASE_REJECTED,
    }

    ACTION_TITLES = {
        AuditAction.CASE_CREATED: "Case created",
        AuditAction.CASE_SUBMITTED: "Case submitted for processing",
        AuditAction.DOCUMENT_UPLOADED: "Document uploaded",
        AuditAction.OCR_COMPLETED: "Document OCR completed",
        AuditAction.EXTRACTION_COMPLETED: "Document field extraction completed",
        AuditAction.VALIDATION_COMPLETED: "Registry and spatial verification completed",
        AuditAction.REVIEW_STARTED: "Officer verification review commenced",
        AuditAction.PROOF_REQUEST_CREATED: "Additional proof requested",
        AuditAction.PROOF_SUBMITTED: "Proof document submitted",
        AuditAction.PROOF_ACCEPTED: "Proof document accepted",
        AuditAction.PROOF_REJECTED: "Proof document rejected",
        AuditAction.CASE_APPROVED: "Property verification approved",
        AuditAction.CASE_REJECTED: "Property verification rejected",
    }

    @staticmethod
    async def record_audit_event(
        db: AsyncSession,
        action: AuditAction,
        case_id: Optional[uuid.UUID] = None,
        actor_id: Optional[uuid.UUID] = None,
        actor_type: AuditActorType = AuditActorType.USER,
        entity_type: Optional[str] = None,
        entity_id: Optional[uuid.UUID] = None,
        old_state: Optional[str] = None,
        new_state: Optional[str] = None,
        metadata_json: Optional[Dict[str, Any]] = None,
    ) -> AuditEvent:
        """Create and append an immutable audit log record."""
        now = datetime.now(timezone.utc)
        audit_event = AuditEvent(
            id=uuid.uuid4(),
            case_id=case_id,
            actor_id=actor_id,
            actor_type=actor_type,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            old_state=old_state,
            new_state=new_state,
            metadata_json=metadata_json,
            created_at=now,
        )
        db.add(audit_event)
        await db.flush()
        return audit_event

    @staticmethod
    async def list_case_audit_events(
        db: AsyncSession,
        case_id: uuid.UUID,
        user: User,
    ) -> List[Dict[str, Any]]:
        """Retrieve audit history for a case, returning full logs for officers and safe timelines for civilians."""
        case_stmt = select(Case).where(Case.id == case_id)
        case_res = await db.execute(case_stmt)
        case = case_res.scalar_one_or_none()
        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Case not found.",
            )
        await CaseAccessService.verify_case_access(db, user, case)

        stmt = (
            select(AuditEvent)
            .where(AuditEvent.case_id == case_id)
            .order_by(AuditEvent.created_at.asc())
        )
        res = await db.execute(stmt)
        events = list(res.scalars().all())

        if user.role == UserRole.CIVILIAN:
            timeline = []
            for ev in events:
                if ev.action in AuditService.CIVILIAN_SAFE_ACTIONS:
                    timeline.append(
                        {
                            "id": ev.id,
                            "case_id": ev.case_id,
                            "action": ev.action.value,
                            "title": AuditService.ACTION_TITLES.get(ev.action, ev.action.value),
                            "status": ev.new_state or ev.old_state,
                            "created_at": ev.created_at,
                        }
                    )
            return timeline

        # For Officer & Super Admin
        return [
            {
                "id": ev.id,
                "case_id": ev.case_id,
                "actor_id": ev.actor_id,
                "actor_type": ev.actor_type.value,
                "action": ev.action.value,
                "entity_type": ev.entity_type,
                "entity_id": ev.entity_id,
                "old_state": ev.old_state,
                "new_state": ev.new_state,
                "metadata": ev.metadata_json,
                "created_at": ev.created_at,
            }
            for ev in events
        ]
