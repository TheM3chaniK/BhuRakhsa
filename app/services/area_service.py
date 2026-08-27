from typing import Optional, Sequence
import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import logger
from app.core.security import hash_password
from app.models.area import Area
from app.models.area_officer_assignment import AreaOfficerAssignment
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.admin import (
    AdminSummaryResponse,
    AreaStats,
    OfficerStats,
    UserStats,
)
from app.schemas.area import AreaCreate, AreaResponse, AreaUpdate
from app.schemas.pagination import PaginatedResponse


class AreaService:
    """Service handling Geographical Area management, spatial access verification, and administrative metrics."""

    @staticmethod
    async def create_area(db: AsyncSession, data: AreaCreate) -> Area:
        """Create a new geographical area."""
        normalized_code = data.code.strip().upper()

        existing = await db.execute(select(Area).where(Area.code == normalized_code))
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"An area with code '{normalized_code}' already exists.",
            )

        new_area = Area(
            name=data.name.strip(),
            code=normalized_code,
            description=data.description.strip() if data.description else None,
            is_active=True,
        )
        db.add(new_area)
        try:
            await db.commit()
            await db.refresh(new_area)
        except IntegrityError:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"An area with code '{normalized_code}' already exists.",
            )
        return new_area

    @staticmethod
    async def get_area(db: AsyncSession, area_id: uuid.UUID) -> Area | None:
        """Retrieve an area by its UUID."""
        result = await db.execute(select(Area).where(Area.id == area_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def list_areas(
        db: AsyncSession,
        page: int = 1,
        page_size: int = 20,
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
    ) -> PaginatedResponse[AreaResponse]:
        """List geographical areas with pagination, status filter, and text search."""
        query = select(Area)
        count_query = select(func.count()).select_from(Area)

        if is_active is not None:
            query = query.where(Area.is_active == is_active)
            count_query = count_query.where(Area.is_active == is_active)

        if search:
            pattern = f"%{search.strip()}%"
            search_clause = or_(
                Area.name.ilike(pattern),
                Area.code.ilike(pattern),
                Area.description.ilike(pattern),
            )
            query = query.where(search_clause)
            count_query = count_query.where(search_clause)

        total_res = await db.execute(count_query)
        total = total_res.scalar() or 0

        query = (
            query.order_by(Area.name.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        res = await db.execute(query)
        areas = res.scalars().all()

        items = [AreaResponse.model_validate(a) for a in areas]
        return PaginatedResponse.create(
            items=items, total=total, page=page, page_size=page_size
        )

    @staticmethod
    async def update_area(
        db: AsyncSession, area_id: uuid.UUID, data: AreaUpdate
    ) -> Area:
        """Update an existing geographical area."""
        area = await AreaService.get_area(db, area_id)
        if not area:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Geographical Area not found.",
            )

        if data.name is not None:
            area.name = data.name.strip()
        if data.description is not None:
            area.description = data.description.strip() if data.description else None
        if data.is_active is not None:
            if data.is_active is False and area.is_active is True:
                # Check for in-flight active cases
                active_cases_stmt = select(func.count(Case.id)).where(
                    Case.area_id == area_id,
                    Case.status.in_([
                        CaseStatus.SUBMITTED,
                        CaseStatus.PROCESSING,
                        CaseStatus.REVIEW_READY,
                        CaseStatus.UNDER_REVIEW,
                        CaseStatus.PROOF_REQUIRED,
                    ]),
                )
                active_cases_count = (await db.execute(active_cases_stmt)).scalar() or 0
                if active_cases_count > 0:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Cannot deactivate area '{area.name}'. There are {active_cases_count} active in-flight cases that must be finalized first.",
                    )
            area.is_active = data.is_active

        await db.commit()
        await db.refresh(area)
        return area

    @staticmethod
    async def deactivate_area(db: AsyncSession, area_id: uuid.UUID) -> Area:
        """Soft delete / deactivate a geographical area."""
        area = await AreaService.get_area(db, area_id)
        if not area:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Geographical Area not found.",
            )

        # Check for in-flight active cases
        active_cases_stmt = select(func.count(Case.id)).where(
            Case.area_id == area_id,
            Case.status.in_([
                CaseStatus.SUBMITTED,
                CaseStatus.PROCESSING,
                CaseStatus.REVIEW_READY,
                CaseStatus.UNDER_REVIEW,
                CaseStatus.PROOF_REQUIRED,
            ]),
        )
        active_cases_count = (await db.execute(active_cases_stmt)).scalar() or 0
        if active_cases_count > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot deactivate area '{area.name}'. There are {active_cases_count} active in-flight cases that must be finalized first.",
            )

        area.is_active = False
        await db.commit()
        await db.refresh(area)
        return area

    @staticmethod
    async def check_officer_area_access(
        db: AsyncSession, user: User, area_id: uuid.UUID
    ) -> bool:
        """Verify if user has authority over a specific geographical area."""
        if user.role == UserRole.SUPER_ADMIN:
            return True

        if user.role == UserRole.AREA_OFFICER:
            query = select(AreaOfficerAssignment).where(
                AreaOfficerAssignment.officer_id == user.id,
                AreaOfficerAssignment.area_id == area_id,
            )
            result = await db.execute(query)
            return result.scalar_one_or_none() is not None

        return False

    @staticmethod
    async def get_admin_summary(db: AsyncSession) -> AdminSummaryResponse:
        """Compute aggregate system metrics across users, areas, and officer assignments."""
        # 1. User metrics
        u_total = (await db.execute(select(func.count()).select_from(User))).scalar() or 0
        u_civilians = (
            await db.execute(
                select(func.count())
                .select_from(User)
                .where(User.role == UserRole.CIVILIAN)
            )
        ).scalar() or 0
        u_officers = (
            await db.execute(
                select(func.count())
                .select_from(User)
                .where(User.role == UserRole.AREA_OFFICER)
            )
        ).scalar() or 0
        u_admins = (
            await db.execute(
                select(func.count())
                .select_from(User)
                .where(User.role == UserRole.SUPER_ADMIN)
            )
        ).scalar() or 0
        u_active = (
            await db.execute(
                select(func.count())
                .select_from(User)
                .where(User.is_active.is_(True))
            )
        ).scalar() or 0
        u_inactive = (
            await db.execute(
                select(func.count())
                .select_from(User)
                .where(User.is_active.is_(False))
            )
        ).scalar() or 0

        # 2. Area metrics
        a_total = (await db.execute(select(func.count()).select_from(Area))).scalar() or 0
        a_active = (
            await db.execute(
                select(func.count())
                .select_from(Area)
                .where(Area.is_active.is_(True))
            )
        ).scalar() or 0
        a_inactive = (
            await db.execute(
                select(func.count())
                .select_from(Area)
                .where(Area.is_active.is_(False))
            )
        ).scalar() or 0

        # 3. Officer assignment metrics
        assigned_officers_count = (
            await db.execute(
                select(func.count(AreaOfficerAssignment.officer_id.distinct()))
            )
        ).scalar() or 0
        unassigned_officers_count = max(0, u_officers - assigned_officers_count)

        return AdminSummaryResponse(
            users=UserStats(
                total=u_total,
                civilians=u_civilians,
                area_officers=u_officers,
                super_admins=u_admins,
                active=u_active,
                inactive=u_inactive,
            ),
            areas=AreaStats(
                total=a_total,
                active=a_active,
                inactive=a_inactive,
            ),
            officers=OfficerStats(
                assigned=assigned_officers_count,
                unassigned=unassigned_officers_count,
            ),
        )

    @staticmethod
    async def seed_initial_super_admin(db: AsyncSession) -> User | None:
        """Bootstrap initial Super Admin account if not present."""
        admin_email = settings.INITIAL_ADMIN_EMAIL.strip().lower()
        query = select(User).where(User.email == admin_email)
        result = await db.execute(query)
        existing = result.scalar_one_or_none()

        if existing is None:
            logger.info("Seeding initial Super Admin: %s", admin_email)
            admin_user = User(
                full_name="Super Administrator",
                email=admin_email,
                password_hash=hash_password(settings.INITIAL_ADMIN_PASSWORD),
                role=UserRole.SUPER_ADMIN,
                is_active=True,
                is_verified=True,
            )
            db.add(admin_user)
            try:
                await db.commit()
                await db.refresh(admin_user)
                return admin_user
            except IntegrityError:
                await db.rollback()
        return existing
