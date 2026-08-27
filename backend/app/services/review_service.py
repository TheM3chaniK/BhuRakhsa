from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import uuid

from fastapi import HTTPException, status
from sqlalchemy import case as sql_case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import logger
from app.events.outbox import OutboxService
from app.models.area_officer_assignment import AreaOfficerAssignment
from app.models.case import Case
from app.models.document import Document
from app.models.enums import (
    AuditAction,
    AuditActorType,
    CaseStatus,
    OfficerDecision,
    ReviewAction,
    ReviewStatus,
    RiskAssessmentStatus,
    RiskLevel,
    UserRole,
    ValidationType,
)
from app.models.final_decision import FinalDecision
from app.models.mismatch import Mismatch
from app.models.property_profile import PropertyProfile
from app.models.review import CaseReview
from app.models.review_history import ReviewHistory
from app.models.risk_assessment import RiskAssessment
from app.models.user import User
from app.models.validation import ValidationRun
from app.schemas.case import CaseResponse
from app.schemas.document import DocumentResponse
from app.schemas.property_profile import PropertyProfileResponse
from app.schemas.review import (
    CaseReviewResponse,
    ReviewDetailResponse,
    ReviewHistoryResponse,
    ReviewQueueItemResponse,
    ReviewQueueResponse,
    SubmitDecisionRequest,
)
from app.schemas.risk import MismatchResponse, RiskAssessmentResponse
from app.schemas.validation import ValidationRunDetailResponse
from app.services.audit_service import AuditService
from app.services.case_access_service import CaseAccessService
from app.services.review_readiness import ReviewReadinessService


class ReviewService:
    """Service orchestrating the Area Officer verification review queue, concurrent assignment locking, holistic context assembly, and decision audit logs."""

    @staticmethod
    async def get_review_queue(
        db: AsyncSession,
        user: User,
        risk_level: Optional[RiskLevel] = None,
        case_status: Optional[CaseStatus] = None,
        review_status: Optional[ReviewStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> ReviewQueueResponse:
        """Fetch queue of review-ready cases within the requesting officer's assigned jurisdiction ordered by risk severity."""
        if user.role == UserRole.CIVILIAN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Civilians do not have access to the review queue.",
            )

        # 1. Determine authorized areas
        authorized_area_ids: Optional[List[uuid.UUID]] = None
        if user.role == UserRole.AREA_OFFICER:
            assign_stmt = select(AreaOfficerAssignment.area_id).where(
                AreaOfficerAssignment.officer_id == user.id,
            )
            assign_res = await db.execute(assign_stmt)
            authorized_area_ids = list(assign_res.scalars().all())
            if not authorized_area_ids:
                return ReviewQueueResponse(items=[], total=0)

        # 2. Build base query for cases
        stmt = (
            select(
                Case,
                CaseReview,
                RiskAssessment,
            )
            .outerjoin(
                CaseReview,
                CaseReview.case_id == Case.id,
            )
            .outerjoin(
                RiskAssessment,
                (RiskAssessment.case_id == Case.id) & (RiskAssessment.status == RiskAssessmentStatus.COMPLETED),
            )
        )

        if case_status:
            stmt = stmt.where(Case.status == case_status)
        else:
            stmt = stmt.where(Case.status != CaseStatus.DRAFT)

        if authorized_area_ids is not None:
            stmt = stmt.where(Case.area_id.in_(authorized_area_ids))

        if risk_level:
            stmt = stmt.where(Case.risk_level == risk_level)

        if case_status:
            stmt = stmt.where(Case.status == case_status)

        if review_status:
            if review_status == ReviewStatus.NOT_STARTED:
                stmt = stmt.where(
                    (CaseReview.status.is_(None)) | (CaseReview.status == ReviewStatus.NOT_STARTED)
                )
            else:
                stmt = stmt.where(CaseReview.status == review_status)

        # 3. Order by risk priority (CRITICAL -> HIGH -> MEDIUM -> LOW -> UNKNOWN) then oldest case
        risk_priority = sql_case(
            (Case.risk_level == RiskLevel.CRITICAL, 1),
            (Case.risk_level == RiskLevel.HIGH, 2),
            (Case.risk_level == RiskLevel.MEDIUM, 3),
            (Case.risk_level == RiskLevel.LOW, 4),
            else_=5,
        )
        stmt = stmt.order_by(risk_priority.asc(), Case.created_at.asc())

        # Total count
        count_stmt = select(func.count()).select_from(stmt.subquery())
        count_res = await db.execute(count_stmt)
        total = count_res.scalar() or 0

        # Paginate
        stmt = stmt.limit(limit).offset(offset)
        res = await db.execute(stmt)
        rows = res.all()

        items: List[ReviewQueueItemResponse] = []
        for case_obj, review_obj, risk_obj in rows:
            r_score = risk_obj.risk_score if risk_obj else 0
            r_level = case_obj.risk_level
            rev_stat = review_obj.status if review_obj else ReviewStatus.NOT_STARTED
            rev_id = review_obj.reviewer_id if review_obj else None

            items.append(
                ReviewQueueItemResponse(
                    case_id=case_obj.id,
                    case_number=case_obj.case_number,
                    title=case_obj.title,
                    area_id=case_obj.area_id,
                    risk_score=r_score,
                    risk_level=r_level,
                    case_status=case_obj.status,
                    review_status=rev_stat,
                    reviewer_id=rev_id,
                    created_at=case_obj.created_at,
                )
            )

        return ReviewQueueResponse(items=items, total=total)

    @staticmethod
    async def start_review(
        db: AsyncSession, case_id: uuid.UUID, user: User
    ) -> CaseReview:
        """Acquire review lock on a case, mark review in progress, and record audit log."""
        if user.role == UserRole.CIVILIAN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Civilians cannot review cases.",
            )

        # 1. Fetch case and verify area jurisdiction
        case_stmt = select(Case).where(Case.id == case_id)
        case_res = await db.execute(case_stmt)
        case_obj = case_res.scalar_one_or_none()
        if not case_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Case not found.",
            )
        await CaseAccessService.verify_case_access(db, user, case_obj)

        if case_obj.status in (CaseStatus.APPROVED, CaseStatus.REJECTED, CaseStatus.CLOSED):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Case is already finalized and cannot be reviewed.",
            )

        # 2. Verify case review readiness
        is_ready, unready_reason = await ReviewReadinessService.is_ready_for_review(db, case_id)
        if not is_ready:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Case is not ready for review: {unready_reason}",
            )

        # 3. Check existing active review for concurrency conflict
        rev_stmt = select(CaseReview).where(
            CaseReview.case_id == case_id,
            CaseReview.status != ReviewStatus.COMPLETED,
        )
        rev_res = await db.execute(rev_stmt)
        review = rev_res.scalar_one_or_none()

        now = datetime.now(timezone.utc)

        if review:
            if review.status == ReviewStatus.IN_PROGRESS and review.reviewer_id and review.reviewer_id != user.id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Case review is already in progress by another officer.",
                )
            old_status = review.status
            review.status = ReviewStatus.IN_PROGRESS
            review.reviewer_id = user.id
            review.reviewer_area_id = case_obj.area_id
            review.started_at = now
        else:
            old_status = ReviewStatus.NOT_STARTED
            review = CaseReview(
                id=uuid.uuid4(),
                case_id=case_id,
                reviewer_id=user.id,
                reviewer_area_id=case_obj.area_id,
                status=ReviewStatus.IN_PROGRESS,
                started_at=now,
            )
            db.add(review)
            await db.flush()

        # Update case status to UNDER_REVIEW
        old_case_status = case_obj.status.value
        case_obj.status = CaseStatus.UNDER_REVIEW
        case_obj.reviewed_by = user.id

        # 4. Record audit history
        audit = ReviewHistory(
            id=uuid.uuid4(),
            case_id=case_id,
            review_id=review.id,
            actor_id=user.id,
            action=ReviewAction.REVIEW_STARTED,
            old_status=old_status,
            new_status=ReviewStatus.IN_PROGRESS,
            reason="Review session commenced by officer.",
            created_at=now,
        )
        db.add(audit)

        # Record domain audit event
        await AuditService.record_audit_event(
            db=db,
            action=AuditAction.REVIEW_STARTED,
            case_id=case_id,
            actor_id=user.id,
            actor_type=AuditActorType.USER,
            entity_type="review",
            entity_id=review.id,
            old_state=old_case_status,
            new_state=CaseStatus.UNDER_REVIEW.value,
            metadata_json={"review_id": str(review.id)},
        )

        await db.commit()
        await db.refresh(review)

        logger.info(
            "Officer %s started review %s for case %s (area %s).",
            user.id,
            review.id,
            case_id,
            case_obj.area_id,
        )
        return review

    @staticmethod
    async def submit_decision(
        db: AsyncSession,
        case_id: uuid.UUID,
        payload: SubmitDecisionRequest,
        user: User,
    ) -> Tuple[CaseReview, CaseStatus]:
        """Submit final officer determination (APPROVE / REJECT / REQUEST_PROOF) with immutable audit snapshot and outbox event."""
        if user.role == UserRole.CIVILIAN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Civilians cannot submit review decisions.",
            )

        case_stmt = select(Case).where(Case.id == case_id)
        case_res = await db.execute(case_stmt)
        case_obj = case_res.scalar_one_or_none()
        if not case_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Case not found.",
            )
        await CaseAccessService.verify_case_access(db, user, case_obj)

        if case_obj.status in (CaseStatus.APPROVED, CaseStatus.REJECTED, CaseStatus.CLOSED):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Case is already finalized and cannot accept further decisions.",
            )

        # 1. Fetch active review
        rev_stmt = select(CaseReview).where(
            CaseReview.case_id == case_id,
            CaseReview.status == ReviewStatus.IN_PROGRESS,
        )
        rev_res = await db.execute(rev_stmt)
        review = rev_res.scalar_one_or_none()
        if not review:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="No in-progress review session found for this case.",
            )

        # Ensure officer owns review unless Super Admin
        if user.role == UserRole.AREA_OFFICER and review.reviewer_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not the assigned reviewer for this review session.",
            )

        # 2. Verify pipeline prerequisites
        is_ready, unready_reason = await ReviewReadinessService.is_ready_for_review(db, case_id)
        if not is_ready:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot submit decision: {unready_reason}",
            )

        # 3. Capture snapshots at decision time
        risk_stmt = (
            select(RiskAssessment)
            .where(
                RiskAssessment.case_id == case_id,
                RiskAssessment.status == RiskAssessmentStatus.COMPLETED,
            )
            .order_by(RiskAssessment.calculated_at.desc())
        )
        risk_res = await db.execute(risk_stmt)
        latest_risk = risk_res.scalars().first()

        db_run_stmt = (
            select(ValidationRun)
            .join(ValidationRun.property_profile)
            .where(
                PropertyProfile.case_id == case_id,
                ValidationRun.validation_type == ValidationType.DATABASE,
            )
            .order_by(ValidationRun.created_at.desc())
        )
        db_run_res = await db.execute(db_run_stmt)
        latest_db_run = db_run_res.scalars().first()

        gis_run_stmt = (
            select(ValidationRun)
            .join(ValidationRun.property_profile)
            .where(
                PropertyProfile.case_id == case_id,
                ValidationRun.validation_type == ValidationType.GIS,
            )
            .order_by(ValidationRun.created_at.desc())
        )
        gis_run_res = await db.execute(gis_run_stmt)
        latest_gis_run = gis_run_res.scalars().first()

        now = datetime.now(timezone.utc)

        # 4. Update review record
        old_decision = review.decision
        review.decision = payload.decision
        review.decision_reason = payload.reason
        review.status = ReviewStatus.COMPLETED
        review.completed_at = now
        if latest_risk:
            review.risk_score_at_decision = latest_risk.risk_score
            review.risk_level_at_decision = latest_risk.risk_level
            review.risk_assessment_id = latest_risk.id
        if latest_db_run:
            review.database_validation_run_id = latest_db_run.id
        if latest_gis_run:
            review.gis_validation_run_id = latest_gis_run.id

        old_case_status = case_obj.status.value

        # 5. Transition case lifecycle state
        if payload.decision == OfficerDecision.APPROVE:
            case_obj.status = CaseStatus.APPROVED
        elif payload.decision == OfficerDecision.REJECT:
            case_obj.status = CaseStatus.REJECTED
        elif payload.decision == OfficerDecision.REQUEST_PROOF:
            case_obj.status = CaseStatus.PROOF_REQUIRED

        case_obj.reviewed_at = now
        case_obj.reviewed_by = user.id

        # 6. Record immutable review history log
        audit = ReviewHistory(
            id=uuid.uuid4(),
            case_id=case_id,
            review_id=review.id,
            actor_id=user.id,
            action=ReviewAction.DECISION_SUBMITTED,
            old_status=ReviewStatus.IN_PROGRESS,
            new_status=ReviewStatus.COMPLETED,
            old_decision=old_decision,
            new_decision=payload.decision,
            reason=payload.reason,
            created_at=now,
        )
        db.add(audit)

        # 7. If terminal decision (APPROVE or REJECT), create FinalDecision, domain audit events, and outbox event
        if payload.decision in (OfficerDecision.APPROVE, OfficerDecision.REJECT):
            final_dec = FinalDecision(
                id=uuid.uuid4(),
                case_id=case_id,
                review_id=review.id,
                decided_by=user.id,
                decision=payload.decision,
                reason=payload.reason,
                risk_assessment_id=latest_risk.id if latest_risk else None,
                risk_score_at_decision=latest_risk.risk_score if latest_risk else None,
                risk_level_at_decision=latest_risk.risk_level if latest_risk else None,
                database_validation_run_id=latest_db_run.id if latest_db_run else None,
                gis_validation_run_id=latest_gis_run.id if latest_gis_run else None,
                property_profile_version=latest_risk.property_profile_version if latest_risk else 1,
                decided_at=now,
                created_at=now,
            )
            db.add(final_dec)

            # Record Audit event for final decision creation
            await AuditService.record_audit_event(
                db=db,
                action=AuditAction.FINAL_DECISION_CREATED,
                case_id=case_id,
                actor_id=user.id,
                actor_type=AuditActorType.USER,
                entity_type="final_decision",
                entity_id=final_dec.id,
                old_state=old_case_status,
                new_state=case_obj.status.value,
                metadata_json={
                    "decision": payload.decision.value,
                    "reason": payload.reason,
                    "risk_score": latest_risk.risk_score if latest_risk else None,
                    "risk_level": latest_risk.risk_level.value if latest_risk and latest_risk.risk_level else None,
                },
            )

            # Record terminal audit event & Outbox event
            if payload.decision == OfficerDecision.APPROVE:
                await AuditService.record_audit_event(
                    db=db,
                    action=AuditAction.CASE_APPROVED,
                    case_id=case_id,
                    actor_id=user.id,
                    actor_type=AuditActorType.USER,
                    entity_type="case",
                    entity_id=case_id,
                    old_state=old_case_status,
                    new_state=CaseStatus.APPROVED.value,
                    metadata_json={"decision": "approve"},
                )
                await OutboxService.record_event(
                    db=db,
                    event_type="CaseApprovedEvent",
                    aggregate_type="case",
                    aggregate_id=case_id,
                    payload={
                        "case_id": str(case_id),
                        "review_id": str(review.id),
                        "decided_by": str(user.id),
                        "owner_id": str(case_obj.created_by),
                        "reason": payload.reason,
                        "risk_score": latest_risk.risk_score if latest_risk else None,
                        "risk_level": latest_risk.risk_level.value if latest_risk and latest_risk.risk_level else None,
                    },
                )
            else:
                await AuditService.record_audit_event(
                    db=db,
                    action=AuditAction.CASE_REJECTED,
                    case_id=case_id,
                    actor_id=user.id,
                    actor_type=AuditActorType.USER,
                    entity_type="case",
                    entity_id=case_id,
                    old_state=old_case_status,
                    new_state=CaseStatus.REJECTED.value,
                    metadata_json={"decision": "reject", "reason": payload.reason},
                )
                await OutboxService.record_event(
                    db=db,
                    event_type="CaseRejectedEvent",
                    aggregate_type="case",
                    aggregate_id=case_id,
                    payload={
                        "case_id": str(case_id),
                        "review_id": str(review.id),
                        "decided_by": str(user.id),
                        "owner_id": str(case_obj.created_by),
                        "reason": payload.reason,
                        "risk_score": latest_risk.risk_score if latest_risk else None,
                        "risk_level": latest_risk.risk_level.value if latest_risk and latest_risk.risk_level else None,
                    },
                )
        else:
            # Intermediate decision REQUEST_PROOF
            await AuditService.record_audit_event(
                db=db,
                action=AuditAction.REVIEW_DECISION_SUBMITTED,
                case_id=case_id,
                actor_id=user.id,
                actor_type=AuditActorType.USER,
                entity_type="review",
                entity_id=review.id,
                old_state=old_case_status,
                new_state=CaseStatus.PROOF_REQUIRED.value,
                metadata_json={"decision": "request_proof", "reason": payload.reason},
            )

        await db.commit()
        await db.refresh(review)

        logger.info(
            "Review %s for case %s completed with decision %s by officer %s.",
            review.id,
            case_id,
            payload.decision.value,
            user.id,
        )
        return review, case_obj.status

    @staticmethod
    async def get_review_context(
        db: AsyncSession, case_id: uuid.UUID, user: User
    ) -> Dict[str, Any]:
        """Assemble holistic case review package across all evidence, extractions, validations, and risk factors."""
        case_stmt = select(Case).where(Case.id == case_id)
        case_res = await db.execute(case_stmt)
        case_obj = case_res.scalar_one_or_none()
        if not case_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Case not found.",
            )
        await CaseAccessService.verify_case_access(db, user, case_obj)

        # 1. Review record
        rev_stmt = select(CaseReview).where(CaseReview.case_id == case_id).order_by(CaseReview.created_at.desc())
        rev_res = await db.execute(rev_stmt)
        review = rev_res.scalars().first()

        # 2. Property profile
        prof_stmt = (
            select(PropertyProfile)
            .where(PropertyProfile.case_id == case_id)
            .options(
                selectinload(PropertyProfile.owners),
                selectinload(PropertyProfile.field_sources),
                selectinload(PropertyProfile.conflicts),
            )
        )
        prof_res = await db.execute(prof_stmt)
        profile = prof_res.scalar_one_or_none()

        # 3. Documents
        docs_stmt = select(Document).where(
            Document.case_id == case_id,
            Document.deleted_at.is_(None),
        ).order_by(Document.created_at.asc())
        docs_res = await db.execute(docs_stmt)
        documents = list(docs_res.scalars().all())

        # 4. Validations
        db_val = None
        gis_val = None
        if profile:
            v_stmt = (
                select(ValidationRun)
                .where(ValidationRun.property_profile_id == profile.id)
                .options(
                    selectinload(ValidationRun.results),
                    selectinload(ValidationRun.candidates),
                )
                .order_by(ValidationRun.created_at.desc())
            )
            v_res = await db.execute(v_stmt)
            runs = v_res.scalars().all()
            for r in runs:
                if r.validation_type == ValidationType.DATABASE and db_val is None:
                    db_val = r
                elif r.validation_type == ValidationType.GIS and gis_val is None:
                    gis_val = r

        # 5. Mismatches
        m_stmt = (
            select(Mismatch)
            .where(Mismatch.case_id == case_id)
            .options(selectinload(Mismatch.evidence_links))
            .order_by(Mismatch.severity.desc(), Mismatch.created_at.desc())
        )
        m_res = await db.execute(m_stmt)
        mismatches = list(m_res.scalars().all())

        # 6. Risk assessment
        risk_stmt = (
            select(RiskAssessment)
            .where(
                RiskAssessment.case_id == case_id,
                RiskAssessment.status == RiskAssessmentStatus.COMPLETED,
            )
            .options(selectinload(RiskAssessment.factors))
            .order_by(RiskAssessment.calculated_at.desc())
        )
        risk_res = await db.execute(risk_stmt)
        risk_assessment = risk_res.scalars().first()

        # 7. Audit history
        hist_stmt = (
            select(ReviewHistory)
            .where(ReviewHistory.case_id == case_id)
            .order_by(ReviewHistory.created_at.asc())
        )
        hist_res = await db.execute(hist_stmt)
        history = list(hist_res.scalars().all())

        return {
            "case": CaseResponse.model_validate(case_obj),
            "review": CaseReviewResponse.model_validate(review) if review else None,
            "property_profile": PropertyProfileResponse.model_validate(profile) if profile else None,
            "documents": [DocumentResponse.model_validate(d) for d in documents],
            "database_validation": ValidationRunDetailResponse.model_validate(db_val) if db_val else None,
            "gis_validation": ValidationRunDetailResponse.model_validate(gis_val) if gis_val else None,
            "mismatches": [MismatchResponse.model_validate(m) for m in mismatches],
            "risk_assessment": RiskAssessmentResponse.model_validate(risk_assessment) if risk_assessment else None,
            "history": [ReviewHistoryResponse.model_validate(h) for h in history],
        }

    @staticmethod
    async def get_review_history(
        db: AsyncSession, case_id: uuid.UUID, user: User
    ) -> List[ReviewHistory]:
        """Fetch audit log entries for a case."""
        case_stmt = select(Case).where(Case.id == case_id)
        case_res = await db.execute(case_stmt)
        case_obj = case_res.scalar_one_or_none()
        if not case_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Case not found.",
            )
        await CaseAccessService.verify_case_access(db, user, case_obj)

        stmt = select(ReviewHistory).where(ReviewHistory.case_id == case_id).order_by(ReviewHistory.created_at.asc())
        res = await db.execute(stmt)
        return list(res.scalars().all())
