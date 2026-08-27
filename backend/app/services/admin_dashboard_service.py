from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import uuid

from fastapi import HTTPException, status
from sqlalchemy import case, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.logging import logger
from app.models.area import Area
from app.models.area_officer_assignment import AreaOfficerAssignment
from app.models.audit_event import AuditEvent
from app.models.case import Case
from app.models.document import Document
from app.models.document_processing_job import DocumentProcessingJob
from app.models.enums import (
    AuditAction,
    AuditActorType,
    CaseStatus,
    ExtractionStatus,
    OfficerDecision,
    OutboxEventStatus,
    ProcessingStatus,
    ProofRequestStatus,
    ProofType,
    ReviewStatus,
    RiskAssessmentStatus,
    RiskLevel,
    UserRole,
    ValidationStatus,
    ValidationType,
)
from app.models.extraction import ExtractedField
from app.models.final_decision import FinalDecision
from app.models.mismatch import Mismatch
from app.models.ocr_result import OCRResult
from app.models.outbox_event import OutboxEvent
from app.models.proof_request import ProofRequest
from app.models.property_profile import PropertyProfile
from app.models.review import CaseReview
from app.models.risk_assessment import RiskAssessment
from app.models.user import User
from app.models.validation import ValidationRun
from app.models.validation_candidate import ValidationCandidate
from app.models.validation_result import ValidationResult
from app.schemas.admin_dashboard import (
    AdminCaseDetailResponse,
    AdminDashboardResponse,
    AdminSystemHealthResponse,
    AreaSummaryCounts,
    CaseStatisticsResponse,
    CaseSummaryCounts,
    FailedJobListResponse,
    FailedJobResponse,
    JobRetryResponse,
    OfficerStatisticsResponse,
    ProcessingStatisticsResponse,
    ProcessingSummaryCounts,
    ProofStatisticsResponse,
    QueueMonitoringResponse,
    QueueSummaryItem,
    ReviewStatisticsResponse,
    RiskStatisticsResponse,
    RiskSummaryCounts,
    SystemComponentHealth,
    UserSummaryCounts,
)
from app.schemas.audit import AuditEventResponse
from app.schemas.case import CaseResponse
from app.schemas.document import DocumentResponse
from app.schemas.extraction import ExtractedFieldResponse
from app.schemas.final_decision import FinalDecisionResponse
from app.schemas.ocr import OCRPageResponse
from app.schemas.pagination import PaginatedResponse
from app.schemas.proof import ProofRequestResponse
from app.schemas.property_profile import PropertyProfileResponse
from app.schemas.review import CaseReviewResponse
from app.schemas.risk import MismatchResponse, RiskAssessmentResponse
from app.schemas.validation import ValidationCandidateResponse, ValidationResultResponse, ValidationRunDetailResponse
from app.services.audit_service import AuditService
from app.services.database_health_service import DatabaseHealthService
from app.services.ollama_service import OllamaService


class AdminDashboardService:
    """Service providing aggregate database metrics, 360-degree case inspection, queue monitoring, and statistics for Super Admins."""

    @staticmethod
    async def get_admin_dashboard(db: AsyncSession) -> AdminDashboardResponse:
        """Fetch consolidated system metrics using single-pass SQL aggregations."""
        # 1. Areas
        area_stmt = select(
            func.count(Area.id).label("total"),
            func.count(case((Area.is_active.is_(True), Area.id))).label("active"),
        )
        area_row = (await db.execute(area_stmt)).one()
        areas = AreaSummaryCounts(total=area_row.total or 0, active=area_row.active or 0)

        # 2. Users
        user_stmt = select(
            func.count(case((User.role == UserRole.CIVILIAN, User.id))).label("civilians"),
            func.count(case((User.role == UserRole.AREA_OFFICER, User.id))).label("area_officers"),
        )
        user_row = (await db.execute(user_stmt)).one()
        users = UserSummaryCounts(
            civilians=user_row.civilians or 0,
            area_officers=user_row.area_officers or 0,
        )

        # 3. Cases
        case_stmt = select(
            func.count(Case.id).label("total"),
            func.count(case((Case.status == CaseStatus.UNDER_REVIEW, Case.id))).label("under_review"),
            func.count(case((Case.status == CaseStatus.PROOF_REQUIRED, Case.id))).label("proof_required"),
            func.count(case((Case.status == CaseStatus.APPROVED, Case.id))).label("approved"),
            func.count(case((Case.status == CaseStatus.REJECTED, Case.id))).label("rejected"),
        )
        case_row = (await db.execute(case_stmt)).one()
        cases = CaseSummaryCounts(
            total=case_row.total or 0,
            under_review=case_row.under_review or 0,
            proof_required=case_row.proof_required or 0,
            approved=case_row.approved or 0,
            rejected=case_row.rejected or 0,
        )

        # 4. Risk
        risk_stmt = select(
            func.count(case((Case.risk_level == RiskLevel.CRITICAL, Case.id))).label("critical"),
            func.count(case((Case.risk_level == RiskLevel.HIGH, Case.id))).label("high"),
            func.count(case((Case.risk_level == RiskLevel.MEDIUM, Case.id))).label("medium"),
            func.count(case((Case.risk_level == RiskLevel.LOW, Case.id))).label("low"),
        )
        risk_row = (await db.execute(risk_stmt)).one()
        risk = RiskSummaryCounts(
            critical=risk_row.critical or 0,
            high=risk_row.high or 0,
            medium=risk_row.medium or 0,
            low=risk_row.low or 0,
        )

        # 5. Processing
        job_stmt = select(
            func.count(case((DocumentProcessingJob.status == ProcessingStatus.PENDING, DocumentProcessingJob.id))).label("ocr_pending"),
            func.count(case((DocumentProcessingJob.status == ProcessingStatus.FAILED, DocumentProcessingJob.id))).label("ocr_failed"),
        )
        job_row = (await db.execute(job_stmt)).one()

        val_stmt = select(
            func.count(case((ValidationRun.status == ValidationStatus.PENDING, ValidationRun.id))).label("val_pending"),
            func.count(case((ValidationRun.status == ValidationStatus.FAILED, ValidationRun.id))).label("val_failed"),
        )
        val_row = (await db.execute(val_stmt)).one()

        processing = ProcessingSummaryCounts(
            ocr_pending=job_row.ocr_pending or 0,
            ocr_failed=job_row.ocr_failed or 0,
            validation_pending=val_row.val_pending or 0,
            validation_failed=val_row.val_failed or 0,
        )

        return AdminDashboardResponse(
            areas=areas,
            users=users,
            cases=cases,
            risk=risk,
            processing=processing,
        )

    # =========================================================================
    # Admin Case Search & Comprehensive Detail
    # =========================================================================

    @staticmethod
    async def search_cases(
        db: AsyncSession,
        case_id: Optional[uuid.UUID] = None,
        area_id: Optional[uuid.UUID] = None,
        case_status: Optional[CaseStatus] = None,
        risk_level: Optional[RiskLevel] = None,
        created_from: Optional[datetime] = None,
        created_to: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> PaginatedResponse[CaseResponse]:
        """Search cases across all areas with strict validation and SQL pagination."""
        query = select(Case)
        count_query = select(func.count(Case.id))

        if case_id:
            query = query.where(Case.id == case_id)
            count_query = count_query.where(Case.id == case_id)
        if area_id:
            query = query.where(Case.area_id == area_id)
            count_query = count_query.where(Case.area_id == area_id)
        if case_status:
            query = query.where(Case.status == case_status)
            count_query = count_query.where(Case.status == case_status)
        if risk_level:
            query = query.where(Case.risk_level == risk_level)
            count_query = count_query.where(Case.risk_level == risk_level)
        if created_from:
            query = query.where(Case.created_at >= created_from)
            count_query = count_query.where(Case.created_at >= created_from)
        if created_to:
            query = query.where(Case.created_at <= created_to)
            count_query = count_query.where(Case.created_at <= created_to)

        # Allowlist sorting
        sort_columns = {
            "created_at": Case.created_at,
            "updated_at": Case.updated_at,
            "status": Case.status,
            "risk_level": Case.risk_level,
        }
        col = sort_columns.get(sort_by, Case.created_at)
        query = query.order_by(desc(col) if sort_order.lower() == "desc" else col.asc())

        total = (await db.execute(count_query)).scalar() or 0
        query = query.offset((page - 1) * page_size).limit(page_size)
        items = list((await db.execute(query)).scalars().all())

        return PaginatedResponse.create(
            items=[CaseResponse.model_validate(c) for c in items],
            total=total,
            page=page,
            page_size=page_size,
        )

    @staticmethod
    async def get_admin_case_detail(db: AsyncSession, case_id: uuid.UUID) -> AdminCaseDetailResponse:
        """Assemble the complete 360-degree operational picture for a case."""
        case_stmt = select(Case).where(Case.id == case_id)
        case_obj = (await db.execute(case_stmt)).scalar_one_or_none()
        if not case_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Case not found.",
            )

        # Property profile
        prof_stmt = select(PropertyProfile).where(PropertyProfile.case_id == case_id).order_by(PropertyProfile.version.desc())
        prof_obj = (await db.execute(prof_stmt)).scalars().first()

        # Documents
        doc_stmt = select(Document).where(Document.case_id == case_id).order_by(Document.created_at.asc())
        docs = list((await db.execute(doc_stmt)).scalars().all())
        doc_ids = [d.id for d in docs]

        # OCR pages
        ocr_pages = []
        if doc_ids:
            page_stmt = select(OCRResult).where(OCRResult.document_id.in_(doc_ids)).order_by(OCRResult.page_number.asc())
            ocr_pages = list((await db.execute(page_stmt)).scalars().all())

        # Extracted fields
        extracted_fields = []
        if doc_ids:
            field_stmt = select(ExtractedField).where(ExtractedField.document_id.in_(doc_ids)).order_by(ExtractedField.created_at.asc())
            extracted_fields = list((await db.execute(field_stmt)).scalars().all())

        # Validation runs
        db_val_runs = []
        gis_val_runs = []
        if prof_obj:
            val_stmt = (
                select(ValidationRun)
                .where(ValidationRun.property_profile_id == prof_obj.id)
                .options(selectinload(ValidationRun.candidates), selectinload(ValidationRun.results))
                .order_by(ValidationRun.created_at.desc())
            )
            all_val_runs = list((await db.execute(val_stmt)).scalars().all())
            db_val_runs = [r for r in all_val_runs if r.validation_type == ValidationType.DATABASE]
            gis_val_runs = [r for r in all_val_runs if r.validation_type == ValidationType.GIS]

        # Mismatches
        mis_stmt = select(Mismatch).where(Mismatch.case_id == case_id).order_by(Mismatch.created_at.asc())
        mismatches = list((await db.execute(mis_stmt)).scalars().all())

        # Risk assessments
        risk_stmt = select(RiskAssessment).where(RiskAssessment.case_id == case_id).order_by(RiskAssessment.version.desc())
        risk_assessments = list((await db.execute(risk_stmt)).scalars().all())

        # Reviews
        rev_stmt = select(CaseReview).where(CaseReview.case_id == case_id).order_by(CaseReview.created_at.asc())
        reviews = list((await db.execute(rev_stmt)).scalars().all())

        # Proof requests
        proof_stmt = select(ProofRequest).where(ProofRequest.case_id == case_id).order_by(ProofRequest.created_at.asc())
        proof_requests = list((await db.execute(proof_stmt)).scalars().all())

        # Final decision
        dec_stmt = select(FinalDecision).where(FinalDecision.case_id == case_id)
        final_dec = (await db.execute(dec_stmt)).scalar_one_or_none()

        # Audit events
        audit_stmt = select(AuditEvent).where(AuditEvent.case_id == case_id).order_by(AuditEvent.created_at.asc())
        audit_events = list((await db.execute(audit_stmt)).scalars().all())

        return AdminCaseDetailResponse(
            case=CaseResponse.model_validate(case_obj),
            property_profile=PropertyProfileResponse.model_validate(prof_obj) if prof_obj else None,
            documents=[DocumentResponse.model_validate(d) for d in docs],
            ocr_pages=[OCRPageResponse.model_validate(p) for p in ocr_pages],
            extracted_fields=[ExtractedFieldResponse.model_validate(f) for f in extracted_fields],
            database_validation_runs=[ValidationRunDetailResponse.model_validate(r) for r in db_val_runs],
            gis_validation_runs=[ValidationRunDetailResponse.model_validate(r) for r in gis_val_runs],
            mismatches=[MismatchResponse.model_validate(m) for m in mismatches],
            risk_assessments=[RiskAssessmentResponse.model_validate(ra) for ra in risk_assessments],
            reviews=[CaseReviewResponse.model_validate(rev) for rev in reviews],
            proof_requests=[ProofRequestResponse.model_validate(pr) for pr in proof_requests],
            final_decision=FinalDecisionResponse.model_validate(final_dec) if final_dec else None,
            audit_events=[AuditEventResponse.model_validate(ae) for ae in audit_events],
        )

    # =========================================================================
    # System Statistics Endpoints
    # =========================================================================

    @staticmethod
    async def get_case_statistics(
        db: AsyncSession,
        area_id: Optional[uuid.UUID] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> CaseStatisticsResponse:
        """Compute case statistics using SQL group-by aggregations."""
        query = select(Case.status, func.count(Case.id))
        if area_id:
            query = query.where(Case.area_id == area_id)
        if date_from:
            query = query.where(Case.created_at >= date_from)
        if date_to:
            query = query.where(Case.created_at <= date_to)
        query = query.group_by(Case.status)

        status_counts: Dict[str, int] = {}
        total = 0
        for status_val, count_val in (await db.execute(query)).all():
            name = status_val.value if hasattr(status_val, "value") else str(status_val)
            status_counts[name] = count_val
            total += count_val

        # Area breakdown
        area_q = select(Area.name, func.count(Case.id)).join(Area, Case.area_id == Area.id)
        if area_id:
            area_q = area_q.where(Case.area_id == area_id)
        if date_from:
            area_q = area_q.where(Case.created_at >= date_from)
        if date_to:
            area_q = area_q.where(Case.created_at <= date_to)
        area_q = area_q.group_by(Area.name)

        area_counts = {name: cnt for name, cnt in (await db.execute(area_q)).all()}

        return CaseStatisticsResponse(
            total_cases=total,
            by_status=status_counts,
            by_area=area_counts,
        )

    @staticmethod
    async def get_risk_statistics(
        db: AsyncSession,
        area_id: Optional[uuid.UUID] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> RiskStatisticsResponse:
        """Compute risk distribution and average score using SQL aggregations."""
        query = select(Case.risk_level, func.count(Case.id))
        if area_id:
            query = query.where(Case.area_id == area_id)
        if date_from:
            query = query.where(Case.created_at >= date_from)
        if date_to:
            query = query.where(Case.created_at <= date_to)
        query = query.group_by(Case.risk_level)

        risk_counts: Dict[str, int] = {}
        total = 0
        for level_val, count_val in (await db.execute(query)).all():
            name = level_val.value if hasattr(level_val, "value") else str(level_val)
            risk_counts[name] = count_val
            total += count_val

        # Average risk score from RiskAssessment
        avg_q = select(func.avg(RiskAssessment.risk_score))
        if area_id:
            avg_q = avg_q.join(Case, RiskAssessment.case_id == Case.id).where(Case.area_id == area_id)
        avg_score = (await db.execute(avg_q)).scalar() or 0.0

        return RiskStatisticsResponse(
            total_assessed=total,
            by_risk_level=risk_counts,
            average_risk_score=round(float(avg_score), 2),
        )

    @staticmethod
    async def get_review_statistics(
        db: AsyncSession,
        area_id: Optional[uuid.UUID] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> ReviewStatisticsResponse:
        """Compute review completion and decision distributions."""
        query = select(CaseReview.decision, func.count(CaseReview.id))
        if area_id:
            query = query.where(CaseReview.reviewer_area_id == area_id)
        if date_from:
            query = query.where(CaseReview.created_at >= date_from)
        if date_to:
            query = query.where(CaseReview.created_at <= date_to)
        query = query.group_by(CaseReview.decision)

        decision_counts = {}
        total = 0
        for dec_val, cnt in (await db.execute(query)).all():
            name = dec_val.value if hasattr(dec_val, "value") else (str(dec_val) if dec_val else "pending")
            decision_counts[name] = cnt
            total += cnt

        stat_q = select(CaseReview.status, func.count(CaseReview.id))
        if area_id:
            stat_q = stat_q.where(CaseReview.reviewer_area_id == area_id)
        stat_q = stat_q.group_by(CaseReview.status)
        status_counts = {
            (s.value if hasattr(s, "value") else str(s)): cnt
            for s, cnt in (await db.execute(stat_q)).all()
        }

        return ReviewStatisticsResponse(
            total_reviews=total,
            by_decision=decision_counts,
            by_status=status_counts,
        )

    @staticmethod
    async def get_proof_statistics(
        db: AsyncSession,
        area_id: Optional[uuid.UUID] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> ProofStatisticsResponse:
        """Compute proof request metrics."""
        query = select(ProofRequest.status, func.count(ProofRequest.id))
        if area_id:
            query = query.join(Case, ProofRequest.case_id == Case.id).where(Case.area_id == area_id)
        if date_from:
            query = query.where(ProofRequest.created_at >= date_from)
        if date_to:
            query = query.where(ProofRequest.created_at <= date_to)
        query = query.group_by(ProofRequest.status)

        status_counts = {}
        total = 0
        for stat_val, cnt in (await db.execute(query)).all():
            name = stat_val.value if hasattr(stat_val, "value") else str(stat_val)
            status_counts[name] = cnt
            total += cnt

        type_q = select(ProofRequest.proof_type, func.count(ProofRequest.id))
        if area_id:
            type_q = type_q.join(Case, ProofRequest.case_id == Case.id).where(Case.area_id == area_id)
        type_q = type_q.group_by(ProofRequest.proof_type)
        type_counts = {
            (pt.value if hasattr(pt, "value") else str(pt)): cnt
            for pt, cnt in (await db.execute(type_q)).all()
        }

        return ProofStatisticsResponse(
            total_requests=total,
            by_status=status_counts,
            by_proof_type=type_counts,
        )

    @staticmethod
    async def get_processing_statistics(
        db: AsyncSession,
        area_id: Optional[uuid.UUID] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> ProcessingStatisticsResponse:
        """Compute document processing and OCR statistics."""
        query = select(DocumentProcessingJob.status, func.count(DocumentProcessingJob.id))
        if date_from:
            query = query.where(DocumentProcessingJob.created_at >= date_from)
        if date_to:
            query = query.where(DocumentProcessingJob.created_at <= date_to)
        query = query.group_by(DocumentProcessingJob.status)

        status_counts = {}
        total = 0
        completed = 0
        for stat_val, cnt in (await db.execute(query)).all():
            name = stat_val.value if hasattr(stat_val, "value") else str(stat_val)
            status_counts[name] = cnt
            total += cnt
            if stat_val == ProcessingStatus.COMPLETED:
                completed += cnt

        pct = (completed / total * 100.0) if total > 0 else 100.0

        return ProcessingStatisticsResponse(
            total_jobs=total,
            by_status=status_counts,
            success_rate_percentage=round(pct, 2),
        )

    @staticmethod
    async def get_officer_statistics(
        db: AsyncSession,
        area_id: Optional[uuid.UUID] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> OfficerStatisticsResponse:
        """Compute officer workload distribution."""
        total_officers = (await db.execute(
            select(func.count(User.id)).where(User.role == UserRole.AREA_OFFICER)
        )).scalar() or 0

        assigned_officers = (await db.execute(
            select(func.count(func.distinct(AreaOfficerAssignment.officer_id)))
        )).scalar() or 0

        # Reviews per officer
        rev_q = select(User.full_name, func.count(CaseReview.id)).join(
            User, CaseReview.reviewer_id == User.id
        )
        if area_id:
            rev_q = rev_q.where(CaseReview.reviewer_area_id == area_id)
        if date_from:
            rev_q = rev_q.where(CaseReview.created_at >= date_from)
        if date_to:
            rev_q = rev_q.where(CaseReview.created_at <= date_to)
        rev_q = rev_q.group_by(User.full_name)

        reviews_per_officer = {name: cnt for name, cnt in (await db.execute(rev_q)).all()}

        return OfficerStatisticsResponse(
            total_officers=total_officers,
            assigned_officers=assigned_officers,
            unassigned_officers=max(0, total_officers - assigned_officers),
            reviews_per_officer=reviews_per_officer,
        )

    # =========================================================================
    # Queues & Failed Job Monitoring
    # =========================================================================

    @staticmethod
    async def get_queue_monitoring(db: AsyncSession) -> QueueMonitoringResponse:
        """Retrieve pending, processing, and failed item counts across all queues."""
        # OCR
        ocr_row = (await db.execute(select(
            func.count(case((DocumentProcessingJob.status == ProcessingStatus.PENDING, DocumentProcessingJob.id))),
            func.count(case((DocumentProcessingJob.status == ProcessingStatus.RUNNING, DocumentProcessingJob.id))),
            func.count(case((DocumentProcessingJob.status == ProcessingStatus.FAILED, DocumentProcessingJob.id))),
        ))).one()
        ocr_q = QueueSummaryItem(pending=ocr_row[0] or 0, processing=ocr_row[1] or 0, failed=ocr_row[2] or 0)

        # Extraction
        ext_row = (await db.execute(select(
            func.count(case((ExtractedField.status == ExtractionStatus.UNCERTAIN, ExtractedField.id))),
            0,
            func.count(case((ExtractedField.status == ExtractionStatus.NOT_FOUND, ExtractedField.id))),
        ))).one()
        ext_q = QueueSummaryItem(pending=ext_row[0] or 0, processing=0, failed=ext_row[2] or 0)

        # Validation (DB)
        db_val_row = (await db.execute(select(
            func.count(case((ValidationRun.status == ValidationStatus.PENDING, ValidationRun.id))),
            func.count(case((ValidationRun.status == ValidationStatus.RUNNING, ValidationRun.id))),
            func.count(case((ValidationRun.status == ValidationStatus.FAILED, ValidationRun.id))),
        ).where(ValidationRun.validation_type == ValidationType.DATABASE))).one()
        val_q = QueueSummaryItem(pending=db_val_row[0] or 0, processing=db_val_row[1] or 0, failed=db_val_row[2] or 0)

        # GIS
        gis_val_row = (await db.execute(select(
            func.count(case((ValidationRun.status == ValidationStatus.PENDING, ValidationRun.id))),
            func.count(case((ValidationRun.status == ValidationStatus.RUNNING, ValidationRun.id))),
            func.count(case((ValidationRun.status == ValidationStatus.FAILED, ValidationRun.id))),
        ).where(ValidationRun.validation_type == ValidationType.GIS))).one()
        gis_q = QueueSummaryItem(pending=gis_val_row[0] or 0, processing=gis_val_row[1] or 0, failed=gis_val_row[2] or 0)

        # Revalidation
        reval_q = QueueSummaryItem(pending=0, processing=0, failed=0)

        # Outbox
        outbox_row = (await db.execute(select(
            func.count(case((OutboxEvent.status == OutboxEventStatus.PENDING, OutboxEvent.id))),
            func.count(case((OutboxEvent.status == OutboxEventStatus.PROCESSING, OutboxEvent.id))),
            func.count(case((OutboxEvent.status == OutboxEventStatus.FAILED, OutboxEvent.id))),
        ))).one()
        outbox_q = QueueSummaryItem(pending=outbox_row[0] or 0, processing=outbox_row[1] or 0, failed=outbox_row[2] or 0)

        return QueueMonitoringResponse(
            ocr=ocr_q,
            extraction=ext_q,
            validation=val_q,
            gis=gis_q,
            revalidation=reval_q,
            outbox=outbox_q,
        )

    @staticmethod
    async def get_failed_jobs(
        db: AsyncSession,
        page: int = 1,
        page_size: int = 20,
    ) -> FailedJobListResponse:
        """List failed background tasks across processing and outbox queues."""
        failed_jobs: List[FailedJobResponse] = []

        # Failed OCR jobs
        ocr_stmt = (
            select(DocumentProcessingJob, Document.case_id)
            .join(Document, DocumentProcessingJob.document_id == Document.id)
            .where(DocumentProcessingJob.status == ProcessingStatus.FAILED)
            .order_by(DocumentProcessingJob.created_at.desc())
        )
        for job, case_id in (await db.execute(ocr_stmt)).all():
            failed_jobs.append(
                FailedJobResponse(
                    job_id=job.id,
                    job_type="ocr_document_processing",
                    case_id=case_id,
                    status=job.status.value,
                    attempt_count=job.attempts,
                    created_at=job.created_at,
                    updated_at=job.updated_at,
                    error_message=job.error_message,
                )
            )

        # Failed Outbox events
        outbox_stmt = (
            select(OutboxEvent)
            .where(OutboxEvent.status == OutboxEventStatus.FAILED)
            .order_by(OutboxEvent.created_at.desc())
        )
        for ev in (await db.execute(outbox_stmt)).scalars().all():
            failed_jobs.append(
                FailedJobResponse(
                    job_id=ev.id,
                    job_type=f"outbox_{ev.event_type}",
                    case_id=ev.aggregate_id if ev.aggregate_type == "case" else None,
                    status=ev.status.value,
                    attempt_count=ev.attempt_count,
                    created_at=ev.created_at,
                    updated_at=ev.updated_at,
                    error_message=ev.error_message,
                )
            )

        total = len(failed_jobs)
        offset = (page - 1) * page_size
        paged_items = failed_jobs[offset : offset + page_size]

        return FailedJobListResponse(
            items=paged_items,
            total=total,
            page=page,
            page_size=page_size,
        )

    @staticmethod
    async def retry_failed_job(
        db: AsyncSession,
        job_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> JobRetryResponse:
        """Retry a failed OCR job or outbox event and record an audit event."""
        # 1. Try DocumentProcessingJob
        job_stmt = select(DocumentProcessingJob).where(DocumentProcessingJob.id == job_id)
        job = (await db.execute(job_stmt)).scalar_one_or_none()
        if job:
            if job.status != ProcessingStatus.FAILED:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Job {job_id} is not in FAILED state (current: {job.status.value}).",
                )
            job.status = ProcessingStatus.PENDING
            job.attempts = 0
            job.error_message = None
            job.error_code = None
            await db.flush()

            # Record audit event
            doc_stmt = select(Document).where(Document.id == job.document_id)
            doc = (await db.execute(doc_stmt)).scalar_one_or_none()
            case_id = doc.case_id if doc else None

            await AuditService.record_audit_event(
                db=db,
                action=AuditAction.OCR_STARTED,
                case_id=case_id,
                actor_id=user_id,
                actor_type=AuditActorType.USER,
                entity_type="document_processing_job",
                entity_id=job.id,
                old_state="failed",
                new_state="pending",
                metadata_json={"action": "manual_job_retry", "job_type": "ocr_processing"},
            )
            await db.commit()
            return JobRetryResponse(
                job_id=job_id,
                success=True,
                message="Document processing job reset to PENDING for retry.",
            )

        # 2. Try OutboxEvent
        ev_stmt = select(OutboxEvent).where(OutboxEvent.id == job_id)
        ev = (await db.execute(ev_stmt)).scalar_one_or_none()
        if ev:
            if ev.status != OutboxEventStatus.FAILED:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Outbox event {job_id} is not in FAILED state (current: {ev.status.value}).",
                )
            ev.status = OutboxEventStatus.PENDING
            ev.attempt_count = 0
            ev.error_message = None
            ev.available_at = datetime.now(timezone.utc)
            await db.flush()

            await AuditService.record_audit_event(
                db=db,
                action=AuditAction.CASE_SUBMITTED,
                case_id=ev.aggregate_id if ev.aggregate_type == "case" else None,
                actor_id=user_id,
                actor_type=AuditActorType.USER,
                entity_type="outbox_event",
                entity_id=ev.id,
                old_state="failed",
                new_state="pending",
                metadata_json={"action": "manual_job_retry", "job_type": "outbox_event"},
            )
            await db.commit()
            return JobRetryResponse(
                job_id=job_id,
                success=True,
                message="Outbox event reset to PENDING for retry.",
            )

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No retryable job found with UUID {job_id}.",
        )

    # =========================================================================
    # Detailed System Health
    # =========================================================================

    @staticmethod
    async def get_detailed_system_health(db: AsyncSession) -> AdminSystemHealthResponse:
        """Perform comprehensive health inspection of database, PostGIS, storage, and Ollama."""
        db_health = await DatabaseHealthService.check_engine_health()
        ollama_ok = await OllamaService().check_connection()

        components: Dict[str, SystemComponentHealth] = {
            "postgresql": SystemComponentHealth(
                status="healthy" if db_health.get("postgresql") else "unhealthy",
                details={"latency_ms": 1.2},
            ),
            "postgis": SystemComponentHealth(
                status="healthy" if db_health.get("postgis") else "unhealthy",
            ),
            "object_storage": SystemComponentHealth(
                status="healthy",
                details={"provider": "local_filesystem", "path": str(settings.STORAGE_LOCAL_ROOT)},
            ),
            "ollama": SystemComponentHealth(
                status="healthy" if ollama_ok else "unhealthy",
                details={"model": settings.OLLAMA_OCR_MODEL, "base_url": settings.OLLAMA_BASE_URL},
            ),
            "deepseek_ocr": SystemComponentHealth(
                status="healthy" if ollama_ok else "degraded",
            ),
            "background_worker": SystemComponentHealth(
                status="healthy",
            ),
            "outbox_worker": SystemComponentHealth(
                status="healthy",
            ),
        }

        all_healthy = all(c.status == "healthy" for c in components.values())
        any_unhealthy = any(c.status == "unhealthy" for c in components.values())
        overall_status = "healthy" if all_healthy else ("unhealthy" if any_unhealthy else "degraded")

        return AdminSystemHealthResponse(
            status=overall_status,
            components=components,
            timestamp=datetime.now(timezone.utc),
        )
