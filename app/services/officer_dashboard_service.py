from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid

from fastapi import HTTPException, status
from sqlalchemy import case, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.area_officer_assignment import AreaOfficerAssignment
from app.models.case import Case
from app.models.enums import CaseStatus, RiskLevel
from app.models.proof_request import ProofRequest
from app.models.review import CaseReview
from app.schemas.admin_dashboard import (
    CaseSummaryCounts,
    OfficerDashboardResponse,
    RiskSummaryCounts,
)
from app.schemas.case import CaseResponse
from app.schemas.pagination import PaginatedResponse


class OfficerDashboardService:
    """Service providing area-scoped dashboard statistics and case searches for Area Officers."""

    @staticmethod
    async def get_officer_dashboard(db: AsyncSession, officer_id: uuid.UUID) -> OfficerDashboardResponse:
        """Fetch dashboard metrics strictly scoped to the officer's assigned areas."""
        # 1. Fetch assigned areas
        area_stmt = select(AreaOfficerAssignment.area_id).where(
            AreaOfficerAssignment.officer_id == officer_id
        )
        assigned_areas = list((await db.execute(area_stmt)).scalars().all())

        if not assigned_areas:
            return OfficerDashboardResponse(
                assigned_areas=[],
                cases=CaseSummaryCounts(total=0, under_review=0, proof_required=0, approved=0, rejected=0),
                risk=RiskSummaryCounts(critical=0, high=0, medium=0, low=0),
                queue={"review_ready": 0, "in_progress": 0, "proof_submitted": 0},
            )

        # 2. Cases in assigned areas
        case_stmt = select(
            func.count(Case.id).label("total"),
            func.count(case((Case.status == CaseStatus.UNDER_REVIEW, Case.id))).label("under_review"),
            func.count(case((Case.status == CaseStatus.PROOF_REQUIRED, Case.id))).label("proof_required"),
            func.count(case((Case.status == CaseStatus.APPROVED, Case.id))).label("approved"),
            func.count(case((Case.status == CaseStatus.REJECTED, Case.id))).label("rejected"),
        ).where(Case.area_id.in_(assigned_areas))
        case_row = (await db.execute(case_stmt)).one()
        cases = CaseSummaryCounts(
            total=case_row.total or 0,
            under_review=case_row.under_review or 0,
            proof_required=case_row.proof_required or 0,
            approved=case_row.approved or 0,
            rejected=case_row.rejected or 0,
        )

        # 3. Risk in assigned areas
        risk_stmt = select(
            func.count(case((Case.risk_level == RiskLevel.CRITICAL, Case.id))).label("critical"),
            func.count(case((Case.risk_level == RiskLevel.HIGH, Case.id))).label("high"),
            func.count(case((Case.risk_level == RiskLevel.MEDIUM, Case.id))).label("medium"),
            func.count(case((Case.risk_level == RiskLevel.LOW, Case.id))).label("low"),
        ).where(Case.area_id.in_(assigned_areas))
        risk_row = (await db.execute(risk_stmt)).one()
        risk = RiskSummaryCounts(
            critical=risk_row.critical or 0,
            high=risk_row.high or 0,
            medium=risk_row.medium or 0,
            low=risk_row.low or 0,
        )

        # 4. Review & Proof Queue in assigned areas
        ready_cnt = (await db.execute(
            select(func.count(Case.id)).where(
                Case.area_id.in_(assigned_areas),
                Case.status == CaseStatus.REVIEW_READY,
            )
        )).scalar() or 0

        in_prog_cnt = (await db.execute(
            select(func.count(CaseReview.id)).where(
                CaseReview.reviewer_id == officer_id,
                CaseReview.status == "in_progress",
            )
        )).scalar() or 0

        proof_sub_cnt = (await db.execute(
            select(func.count(ProofRequest.id)).join(Case, ProofRequest.case_id == Case.id).where(
                Case.area_id.in_(assigned_areas),
                ProofRequest.status == "submitted",
            )
        )).scalar() or 0

        queue = {
            "review_ready": ready_cnt,
            "in_progress": in_prog_cnt,
            "proof_submitted": proof_sub_cnt,
        }

        return OfficerDashboardResponse(
            assigned_areas=assigned_areas,
            cases=cases,
            risk=risk,
            queue=queue,
        )

    @staticmethod
    async def search_officer_cases(
        db: AsyncSession,
        officer_id: uuid.UUID,
        case_id: Optional[uuid.UUID] = None,
        case_status: Optional[CaseStatus] = None,
        risk_level: Optional[RiskLevel] = None,
        created_from: Optional[datetime] = None,
        created_to: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> PaginatedResponse[CaseResponse]:
        """Search cases strictly scoped to officer's assigned areas."""
        # 1. Fetch assigned areas
        area_stmt = select(AreaOfficerAssignment.area_id).where(
            AreaOfficerAssignment.officer_id == officer_id
        )
        assigned_areas = list((await db.execute(area_stmt)).scalars().all())

        if not assigned_areas:
            return PaginatedResponse.create(items=[], total=0, page=page, page_size=page_size)

        query = select(Case).where(Case.area_id.in_(assigned_areas))
        count_query = select(func.count(Case.id)).where(Case.area_id.in_(assigned_areas))

        if case_id:
            query = query.where(Case.id == case_id)
            count_query = count_query.where(Case.id == case_id)
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
