from datetime import datetime, timezone
from typing import List, Optional
import uuid

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import logger
from app.events.outbox import OutboxService
from app.models.case import Case
from app.models.document import Document
from app.models.enums import (
    AuditAction,
    AuditActorType,
    CaseStatus,
    DocumentStatus,
    ProofRequestAction,
    ProofRequestStatus,
    ProofSubmissionStatus,
    UserRole,
)
from app.models.proof_request import ProofRequest
from app.models.proof_request_history import ProofRequestHistory
from app.models.proof_submission import ProofSubmission
from app.models.user import User
from app.schemas.proof import (
    ProofCancelRequest,
    ProofRejectRequest,
    ProofRequestCreate,
)
from app.services.audit_service import AuditService
from app.services.case_access_service import CaseAccessService
from app.services.document_processing_service import DocumentProcessingService
from app.services.document_service import DocumentService
from app.services.file_validation_service import FileValidationService


class ProofRequestService:
    """Service managing the formal proof request lifecycle, civilian submissions, and officer determinations."""

    @staticmethod
    async def create_proof_request(
        db: AsyncSession,
        case_id: uuid.UUID,
        payload: ProofRequestCreate,
        user: User,
    ) -> ProofRequest:
        """Create a new evidentiary proof request assigned to the case owner (Area Officer / Super Admin only)."""
        if user.role == UserRole.CIVILIAN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Civilians cannot create proof requests.",
            )

        case_stmt = select(Case).where(Case.id == case_id)
        case_res = await db.execute(case_stmt)
        case = case_res.scalar_one_or_none()
        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Case not found.",
            )
        await CaseAccessService.verify_case_access(db, user, case)

        if case.status in (CaseStatus.APPROVED, CaseStatus.REJECTED, CaseStatus.CLOSED):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot request proof on an already finalized case.",
            )

        now = datetime.now(timezone.utc)
        proof_request = ProofRequest(
            id=uuid.uuid4(),
            case_id=case_id,
            review_id=payload.review_id,
            requested_by=user.id,
            requested_from=case.created_by,
            proof_type=payload.proof_type,
            title=payload.title,
            description=payload.description,
            status=ProofRequestStatus.OPEN,
            due_at=payload.due_at,
            created_at=now,
            updated_at=now,
        )
        db.add(proof_request)
        await db.flush()

        # Transition case lifecycle to PROOF_REQUIRED
        old_case_status = case.status.value
        case.status = CaseStatus.PROOF_REQUIRED

        # Record audit history
        audit = ProofRequestHistory(
            id=uuid.uuid4(),
            proof_request_id=proof_request.id,
            actor_id=user.id,
            actor_type="user",
            action=ProofRequestAction.CREATED,
            old_status=None,
            new_status=ProofRequestStatus.OPEN,
            reason=f"Proof requested by officer: {payload.title}",
            created_at=now,
        )
        db.add(audit)

        # Record domain AuditEvent
        await AuditService.record_audit_event(
            db=db,
            action=AuditAction.PROOF_REQUEST_CREATED,
            case_id=case_id,
            actor_id=user.id,
            actor_type=AuditActorType.USER,
            entity_type="proof_request",
            entity_id=proof_request.id,
            old_state=old_case_status,
            new_state=CaseStatus.PROOF_REQUIRED.value,
            metadata_json={"title": payload.title, "proof_type": payload.proof_type.value},
        )

        # Record domain OutboxEvent
        await OutboxService.record_event(
            db=db,
            event_type="ProofRequestedEvent",
            aggregate_type="proof_request",
            aggregate_id=proof_request.id,
            payload={
                "proof_request_id": str(proof_request.id),
                "case_id": str(case_id),
                "requested_by": str(user.id),
                "requested_from": str(case.created_by),
                "title": payload.title,
                "description": payload.description,
                "proof_type": payload.proof_type.value,
            },
        )

        await db.commit()
        await db.refresh(proof_request)

        logger.info(
            "ProofRequest %s created for case %s by officer %s (civilian: %s).",
            proof_request.id,
            case_id,
            user.id,
            case.created_by,
        )
        return proof_request

    @staticmethod
    async def get_proof_request(
        db: AsyncSession,
        proof_request_id: uuid.UUID,
        user: User,
    ) -> ProofRequest:
        """Fetch proof request details ensuring access authorization."""
        stmt = (
            select(ProofRequest)
            .where(ProofRequest.id == proof_request_id)
            .options(
                selectinload(ProofRequest.submissions),
                selectinload(ProofRequest.case),
            )
        )
        res = await db.execute(stmt)
        proof_request = res.scalar_one_or_none()
        if not proof_request:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Proof request not found.",
            )

        if user.role == UserRole.CIVILIAN and proof_request.requested_from != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to view this proof request.",
            )
        elif user.role == UserRole.AREA_OFFICER:
            await CaseAccessService.verify_case_access(db, user, proof_request.case)

        return proof_request

    @staticmethod
    async def list_case_proof_requests(
        db: AsyncSession,
        case_id: uuid.UUID,
        user: User,
    ) -> List[ProofRequest]:
        """List all proof requests belonging to a case."""
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
            select(ProofRequest)
            .where(ProofRequest.case_id == case_id)
            .options(selectinload(ProofRequest.submissions))
            .order_by(ProofRequest.created_at.desc())
        )
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def submit_proof(
        db: AsyncSession,
        proof_request_id: uuid.UUID,
        file: UploadFile,
        comment: Optional[str],
        user: User,
    ) -> ProofSubmission:
        """Handle civilian file upload responding to an open proof request."""
        stmt = (
            select(ProofRequest)
            .where(ProofRequest.id == proof_request_id)
            .options(selectinload(ProofRequest.case))
        )
        res = await db.execute(stmt)
        proof_request = res.scalar_one_or_none()
        if not proof_request:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Proof request not found.",
            )

        # 1. Authorize submitter
        if user.role != UserRole.CIVILIAN or proof_request.requested_from != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the requested civilian case owner can submit proof.",
            )

        # 2. Check request status & case status
        if proof_request.case.status in (CaseStatus.APPROVED, CaseStatus.REJECTED, CaseStatus.CLOSED):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot submit proof for an already finalized case.",
            )

        if proof_request.status != ProofRequestStatus.OPEN:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Proof request is not open for submission (current status: {proof_request.status.value}).",
            )

        # 3. Read and validate file using Step 7 infrastructure
        file_content = await file.read()
        file_validation = FileValidationService.validate_file(
            filename=file.filename or "unknown",
            file_bytes=file_content,
            mime_type=file.content_type,
        )

        # 4. Store document securely
        storage = DocumentService.get_storage_service()
        storage_key = await storage.save_file(
            case_id=proof_request.case_id,
            filename=file_validation.sanitized_filename,
            file_bytes=file_content,
        )

        now = datetime.now(timezone.utc)
        doc_id = uuid.uuid4()
        document = Document(
            id=doc_id,
            case_id=proof_request.case_id,
            proof_request_id=proof_request.id,
            original_filename=file_validation.sanitized_filename,
            stored_filename=storage_key.split("/")[-1],
            mime_type=file_validation.mime_type,
            file_extension=file_validation.file_extension,
            file_size=file_validation.file_size,
            sha256_hash=file_validation.sha256_hash,
            storage_backend="local",
            storage_key=storage_key,
            status=DocumentStatus.QUEUED,
            uploaded_by=user.id,
            created_at=now,
            updated_at=now,
        )
        db.add(document)
        await db.flush()

        # 5. Create ProofSubmission
        submission = ProofSubmission(
            id=uuid.uuid4(),
            proof_request_id=proof_request.id,
            submitted_by=user.id,
            document_id=document.id,
            status=ProofSubmissionStatus.PROCESSING,
            comment=comment,
            submitted_at=now,
            created_at=now,
            updated_at=now,
        )
        db.add(submission)

        # 6. Update ProofRequest status to SUBMITTED
        old_status = proof_request.status
        proof_request.status = ProofRequestStatus.SUBMITTED

        # 7. Record audit history
        audit = ProofRequestHistory(
            id=uuid.uuid4(),
            proof_request_id=proof_request.id,
            actor_id=user.id,
            actor_type="user",
            action=ProofRequestAction.SUBMITTED,
            old_status=old_status,
            new_status=ProofRequestStatus.SUBMITTED,
            reason=f"Civilian submitted document '{file_validation.sanitized_filename}'.",
            created_at=now,
        )
        db.add(audit)

        # Record domain AuditEvent
        await AuditService.record_audit_event(
            db=db,
            action=AuditAction.PROOF_SUBMITTED,
            case_id=proof_request.case_id,
            actor_id=user.id,
            actor_type=AuditActorType.USER,
            entity_type="proof_submission",
            entity_id=submission.id,
            old_state=old_status.value,
            new_state=ProofRequestStatus.SUBMITTED.value,
            metadata_json={"document_id": str(document.id), "filename": file_validation.sanitized_filename},
        )

        # Record domain OutboxEvent
        await OutboxService.record_event(
            db=db,
            event_type="ProofSubmittedEvent",
            aggregate_type="proof_submission",
            aggregate_id=submission.id,
            payload={
                "proof_request_id": str(proof_request.id),
                "case_id": str(proof_request.case_id),
                "area_id": str(proof_request.case.area_id),
                "submitted_by": str(user.id),
                "document_id": str(document.id),
            },
        )

        # 8. Queue document processing job (OCR + extraction)
        await DocumentProcessingService.queue_processing_job(
            db=db,
            document_id=document.id,
        )

        await db.commit()
        await db.refresh(submission)

        logger.info(
            "Civilian %s submitted proof submission %s (document %s) for ProofRequest %s.",
            user.id,
            submission.id,
            document.id,
            proof_request.id,
        )
        return submission

    @staticmethod
    async def accept_proof_request(
        db: AsyncSession,
        proof_request_id: uuid.UUID,
        user: User,
    ) -> ProofRequest:
        """Mark a proof request as accepted by the reviewing officer."""
        if user.role == UserRole.CIVILIAN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Civilians cannot accept proof requests.",
            )

        stmt = (
            select(ProofRequest)
            .where(ProofRequest.id == proof_request_id)
            .options(selectinload(ProofRequest.case))
        )
        res = await db.execute(stmt)
        proof_request = res.scalar_one_or_none()
        if not proof_request:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Proof request not found.",
            )
        await CaseAccessService.verify_case_access(db, user, proof_request.case)

        if proof_request.case.status in (CaseStatus.APPROVED, CaseStatus.REJECTED, CaseStatus.CLOSED):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot accept proof on an already finalized case.",
            )

        if proof_request.status in (ProofRequestStatus.ACCEPTED, ProofRequestStatus.REJECTED, ProofRequestStatus.CANCELLED):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Proof request is already finalized (status: {proof_request.status.value}).",
            )

        old_status = proof_request.status
        now = datetime.now(timezone.utc)
        proof_request.status = ProofRequestStatus.ACCEPTED
        proof_request.completed_at = now

        # Check if any remaining open/submitted requests exist for this case
        all_reqs_stmt = select(ProofRequest).where(
            ProofRequest.case_id == proof_request.case_id,
            ProofRequest.id != proof_request.id,
            ProofRequest.status.in_([ProofRequestStatus.OPEN, ProofRequestStatus.SUBMITTED, ProofRequestStatus.UNDER_REVIEW]),
        )
        all_reqs_res = await db.execute(all_reqs_stmt)
        remaining = list(all_reqs_res.scalars().all())

        if not remaining:
            # All requests satisfied; transition case to review ready
            proof_request.case.status = CaseStatus.REVIEW_READY

        audit = ProofRequestHistory(
            id=uuid.uuid4(),
            proof_request_id=proof_request.id,
            actor_id=user.id,
            actor_type="user",
            action=ProofRequestAction.ACCEPTED,
            old_status=old_status,
            new_status=ProofRequestStatus.ACCEPTED,
            reason="Submitted proof reviewed and accepted as sufficient by officer.",
            created_at=now,
        )
        db.add(audit)

        # Record domain AuditEvent
        await AuditService.record_audit_event(
            db=db,
            action=AuditAction.PROOF_ACCEPTED,
            case_id=proof_request.case_id,
            actor_id=user.id,
            actor_type=AuditActorType.USER,
            entity_type="proof_request",
            entity_id=proof_request.id,
            old_state=old_status.value,
            new_state=ProofRequestStatus.ACCEPTED.value,
            metadata_json={"proof_request_id": str(proof_request.id)},
        )

        # Record domain OutboxEvent
        await OutboxService.record_event(
            db=db,
            event_type="ProofAcceptedEvent",
            aggregate_type="proof_request",
            aggregate_id=proof_request.id,
            payload={
                "proof_request_id": str(proof_request.id),
                "case_id": str(proof_request.case_id),
                "accepted_by": str(user.id),
                "requested_from": str(proof_request.requested_from),
            },
        )

        await db.commit()
        await db.refresh(proof_request)

        logger.info(
            "Officer %s accepted proof request %s for case %s.",
            user.id,
            proof_request.id,
            proof_request.case_id,
        )
        return proof_request

    @staticmethod
    async def reject_proof_request(
        db: AsyncSession,
        proof_request_id: uuid.UUID,
        payload: ProofRejectRequest,
        user: User,
    ) -> ProofRequest:
        """Reject a proof submission with mandatory factual reason."""
        if user.role == UserRole.CIVILIAN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Civilians cannot reject proof requests.",
            )

        stmt = (
            select(ProofRequest)
            .where(ProofRequest.id == proof_request_id)
            .options(selectinload(ProofRequest.case))
        )
        res = await db.execute(stmt)
        proof_request = res.scalar_one_or_none()
        if not proof_request:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Proof request not found.",
            )
        await CaseAccessService.verify_case_access(db, user, proof_request.case)

        if proof_request.case.status in (CaseStatus.APPROVED, CaseStatus.REJECTED, CaseStatus.CLOSED):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot reject proof on an already finalized case.",
            )

        if proof_request.status in (ProofRequestStatus.ACCEPTED, ProofRequestStatus.REJECTED, ProofRequestStatus.CANCELLED):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Proof request is already finalized (status: {proof_request.status.value}).",
            )

        old_status = proof_request.status
        now = datetime.now(timezone.utc)
        proof_request.status = ProofRequestStatus.REJECTED
        proof_request.rejection_reason = payload.reason
        proof_request.completed_at = now

        # Case remains in PROOF_REQUIRED
        proof_request.case.status = CaseStatus.PROOF_REQUIRED

        audit = ProofRequestHistory(
            id=uuid.uuid4(),
            proof_request_id=proof_request.id,
            actor_id=user.id,
            actor_type="user",
            action=ProofRequestAction.REJECTED,
            old_status=old_status,
            new_status=ProofRequestStatus.REJECTED,
            reason=payload.reason,
            created_at=now,
        )
        db.add(audit)

        # Record domain AuditEvent
        await AuditService.record_audit_event(
            db=db,
            action=AuditAction.PROOF_REJECTED,
            case_id=proof_request.case_id,
            actor_id=user.id,
            actor_type=AuditActorType.USER,
            entity_type="proof_request",
            entity_id=proof_request.id,
            old_state=old_status.value,
            new_state=ProofRequestStatus.REJECTED.value,
            metadata_json={"reason": payload.reason},
        )

        # Record domain OutboxEvent
        await OutboxService.record_event(
            db=db,
            event_type="ProofRejectedEvent",
            aggregate_type="proof_request",
            aggregate_id=proof_request.id,
            payload={
                "proof_request_id": str(proof_request.id),
                "case_id": str(proof_request.case_id),
                "rejected_by": str(user.id),
                "requested_from": str(proof_request.requested_from),
                "reason": payload.reason,
            },
        )

        await db.commit()
        await db.refresh(proof_request)

        logger.info(
            "Officer %s rejected proof request %s for case %s (reason: %s).",
            user.id,
            proof_request.id,
            proof_request.case_id,
            payload.reason,
        )
        return proof_request

    @staticmethod
    async def cancel_proof_request(
        db: AsyncSession,
        proof_request_id: uuid.UUID,
        payload: ProofCancelRequest,
        user: User,
    ) -> ProofRequest:
        """Cancel an open/unneeded proof request with reason."""
        if user.role == UserRole.CIVILIAN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Civilians cannot cancel proof requests.",
            )

        stmt = (
            select(ProofRequest)
            .where(ProofRequest.id == proof_request_id)
            .options(selectinload(ProofRequest.case))
        )
        res = await db.execute(stmt)
        proof_request = res.scalar_one_or_none()
        if not proof_request:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Proof request not found.",
            )
        await CaseAccessService.verify_case_access(db, user, proof_request.case)

        if proof_request.case.status in (CaseStatus.APPROVED, CaseStatus.REJECTED, CaseStatus.CLOSED):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot cancel proof on an already finalized case.",
            )

        if proof_request.status in (ProofRequestStatus.ACCEPTED, ProofRequestStatus.REJECTED, ProofRequestStatus.CANCELLED):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Proof request is already finalized (status: {proof_request.status.value}).",
            )

        old_status = proof_request.status
        now = datetime.now(timezone.utc)
        proof_request.status = ProofRequestStatus.CANCELLED
        proof_request.cancellation_reason = payload.reason
        proof_request.completed_at = now

        # Check if any remaining open requests exist
        all_reqs_stmt = select(ProofRequest).where(
            ProofRequest.case_id == proof_request.case_id,
            ProofRequest.id != proof_request.id,
            ProofRequest.status.in_([ProofRequestStatus.OPEN, ProofRequestStatus.SUBMITTED, ProofRequestStatus.UNDER_REVIEW]),
        )
        all_reqs_res = await db.execute(all_reqs_stmt)
        remaining = list(all_reqs_res.scalars().all())

        if not remaining:
            proof_request.case.status = CaseStatus.REVIEW_READY

        audit = ProofRequestHistory(
            id=uuid.uuid4(),
            proof_request_id=proof_request.id,
            actor_id=user.id,
            actor_type="user",
            action=ProofRequestAction.CANCELLED,
            old_status=old_status,
            new_status=ProofRequestStatus.CANCELLED,
            reason=payload.reason,
            created_at=now,
        )
        db.add(audit)

        # Record domain AuditEvent
        await AuditService.record_audit_event(
            db=db,
            action=AuditAction.PROOF_CANCELLED,
            case_id=proof_request.case_id,
            actor_id=user.id,
            actor_type=AuditActorType.USER,
            entity_type="proof_request",
            entity_id=proof_request.id,
            old_state=old_status.value,
            new_state=ProofRequestStatus.CANCELLED.value,
            metadata_json={"reason": payload.reason},
        )

        await db.commit()
        await db.refresh(proof_request)

        logger.info(
            "Officer %s cancelled proof request %s for case %s (reason: %s).",
            user.id,
            proof_request.id,
            proof_request.case_id,
            payload.reason,
        )
        return proof_request

    @staticmethod
    async def get_proof_request_history(
        db: AsyncSession,
        proof_request_id: uuid.UUID,
        user: User,
    ) -> List[ProofRequestHistory]:
        """Fetch audit log records for a proof request."""
        req = await ProofRequestService.get_proof_request(db, proof_request_id, user)
        stmt = (
            select(ProofRequestHistory)
            .where(ProofRequestHistory.proof_request_id == req.id)
            .order_by(ProofRequestHistory.created_at.asc())
        )
        res = await db.execute(stmt)
        return list(res.scalars().all())
