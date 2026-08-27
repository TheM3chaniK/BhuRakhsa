from datetime import datetime, timezone
from typing import Optional, Sequence
import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.area import Area
from app.models.area_officer_assignment import AreaOfficerAssignment
from app.models.case import Case, CaseSequence
from app.models.enums import CaseStatus, RiskLevel, UserRole
from app.models.user import User
from app.schemas.case import CaseCreate, CaseResponse, CaseUpdate
from app.schemas.pagination import PaginatedResponse


class CaseService:
    """Service handling Case creation, database-backed numbering, lifecycle transitions, and queries."""

    @staticmethod
    async def generate_case_number(db: AsyncSession, year: int) -> str:
        """Generate consecutive year-aware unique case number (e.g. CASE-2026-000001) safely."""
        # Row-level lock on the sequence record for the year
        seq_query = (
            select(CaseSequence)
            .where(CaseSequence.year == year)
            .with_for_update()
        )
        result = await db.execute(seq_query)
        seq_record = result.scalar_one_or_none()

        if seq_record is None:
            # First case of the year
            seq_record = CaseSequence(year=year, last_value=1)
            db.add(seq_record)
            next_val = 1
        else:
            seq_record.last_value += 1
            next_val = seq_record.last_value

        await db.flush()
        return f"CASE-{year}-{next_val:06d}"

    @staticmethod
    async def create_case(
        db: AsyncSession, user: User, data: CaseCreate
    ) -> Case:
        """Create a new verification case in DRAFT status (Civilian only)."""
        # 1. Validate area
        area_res = await db.execute(select(Area).where(Area.id == data.area_id))
        area = area_res.scalar_one_or_none()
        if not area:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Geographical Area not found.",
            )

        if not area.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot create a case in an inactive geographical area.",
            )

        # 2. Generate unique case number
        current_year = datetime.now(timezone.utc).year
        case_number = await CaseService.generate_case_number(db, current_year)

        # 3. Create Case record
        new_case = Case(
            case_number=case_number,
            created_by=user.id,
            area_id=data.area_id,
            status=CaseStatus.DRAFT,
            risk_level=RiskLevel.UNKNOWN,
            title=data.title,
            description=data.description,
        )
        db.add(new_case)
        try:
            await db.commit()
            await db.refresh(new_case)
        except IntegrityError:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Case could not be created due to a concurrent conflict. Please retry.",
            )
        return new_case

    @staticmethod
    async def get_case(db: AsyncSession, case_id: uuid.UUID) -> Case | None:
        """Retrieve a case by UUID."""
        query = select(Case).where(Case.id == case_id)
        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def list_cases(
        db: AsyncSession,
        user: User,
        page: int = 1,
        page_size: int = 20,
        case_status: Optional[CaseStatus] = None,
        risk_level: Optional[RiskLevel] = None,
        area_id: Optional[uuid.UUID] = None,
    ) -> PaginatedResponse[CaseResponse]:
        """List cases scoped to the user's role and permissions with server-side filtering and pagination."""
        query = select(Case)
        count_query = select(func.count(Case.id.distinct())).select_from(Case)

        # Apply role-based query scoping
        if user.role == UserRole.CIVILIAN:
            query = query.where(Case.created_by == user.id)
            count_query = count_query.where(Case.created_by == user.id)
        elif user.role == UserRole.AREA_OFFICER:
            query = query.join(
                AreaOfficerAssignment,
                Case.area_id == AreaOfficerAssignment.area_id,
            ).where(AreaOfficerAssignment.officer_id == user.id)
            count_query = count_query.join(
                AreaOfficerAssignment,
                Case.area_id == AreaOfficerAssignment.area_id,
            ).where(AreaOfficerAssignment.officer_id == user.id)
        elif user.role == UserRole.SUPER_ADMIN:
            pass  # Unrestricted global access

        # Apply optional filters
        if case_status is not None:
            query = query.where(Case.status == case_status)
            count_query = count_query.where(Case.status == case_status)

        if risk_level is not None:
            query = query.where(Case.risk_level == risk_level)
            count_query = count_query.where(Case.risk_level == risk_level)

        if area_id is not None:
            query = query.where(Case.area_id == area_id)
            count_query = count_query.where(Case.area_id == area_id)

        # Execute total count
        total_res = await db.execute(count_query)
        total = total_res.scalar() or 0

        # Execute paginated query
        query = (
            query.order_by(Case.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        res = await db.execute(query)
        cases = res.scalars().all()

        items = [CaseResponse.model_validate(c) for c in cases]
        return PaginatedResponse.create(
            items=items, total=total, page=page, page_size=page_size
        )

    @staticmethod
    async def update_case(
        db: AsyncSession, case_id: uuid.UUID, user: User, data: CaseUpdate
    ) -> Case:
        """Update draft case attributes (Civilian owner only)."""
        case = await CaseService.get_case(db, case_id)
        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Case not found.",
            )

        # Enforce ownership
        if case.created_by != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the case owner can modify this case.",
            )

        # Enforce draft status immutability
        if case.status != CaseStatus.DRAFT:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Submitted or processed cases cannot be modified.",
            )

        # Validate area if changed
        if data.area_id is not None and data.area_id != case.area_id:
            area_res = await db.execute(select(Area).where(Area.id == data.area_id))
            area = area_res.scalar_one_or_none()
            if not area:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Geographical Area not found.",
                )
            if not area.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot assign case to an inactive geographical area.",
                )
            case.area_id = data.area_id

        if data.title is not None:
            case.title = data.title
        if data.description is not None:
            case.description = data.description

        case.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(case)
        return case

    @staticmethod
    async def submit_case(
        db: AsyncSession, case_id: uuid.UUID, user: User
    ) -> Case:
        """Transition case from DRAFT to SUBMITTED status (Civilian owner only)."""
        case = await CaseService.get_case(db, case_id)
        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Case not found.",
            )

        # Enforce ownership
        if case.created_by != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the case owner can submit this case.",
            )

        # Enforce draft transition rule
        if case.status != CaseStatus.DRAFT:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Case has already been submitted or is not in draft status.",
            )

        # Verify associated area is active
        area_res = await db.execute(select(Area).where(Area.id == case.area_id))
        area = area_res.scalar_one_or_none()
        if not area or not area.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot submit case because the associated geographical area is inactive.",
            )

        now = datetime.now(timezone.utc)
        case.status = CaseStatus.SUBMITTED
        case.submitted_at = now
        case.updated_at = now

        await db.commit()
        await db.refresh(case)
        return case
