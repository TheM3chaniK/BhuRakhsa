from datetime import datetime, timezone
from typing import Optional, Sequence
import uuid

from fastapi import HTTPException, status
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import hash_password
from app.models.area import Area
from app.models.area_officer_assignment import AreaOfficerAssignment
from app.models.enums import UserRole
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.area import AreaResponse
from app.schemas.officer import OfficerCreate, OfficerDetailResponse, OfficerUpdate
from app.schemas.pagination import PaginatedResponse


class OfficerService:
    """Service handling Area Officer provisioning, profile updates, area assignments, and demotion."""

    @staticmethod
    async def create_officer(db: AsyncSession, data: OfficerCreate) -> User:
        """Provision a new Area Officer account (Super Admin only)."""
        normalized_email = data.email.strip().lower()

        existing = await db.execute(select(User).where(User.email == normalized_email))
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A user with this email address already exists.",
            )

        hashed_pwd = hash_password(data.password)
        officer = User(
            full_name=data.full_name.strip(),
            email=normalized_email,
            phone=data.phone.strip() if data.phone else None,
            password_hash=hashed_pwd,
            role=UserRole.AREA_OFFICER,  # Explicitly force AREA_OFFICER
            is_active=True,
            is_verified=True,
        )

        db.add(officer)
        try:
            await db.commit()
            await db.refresh(officer)
        except IntegrityError:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A user with this email address already exists.",
            )
        return officer

    @staticmethod
    async def list_officers(
        db: AsyncSession,
        page: int = 1,
        page_size: int = 20,
        is_active: Optional[bool] = None,
        area_id: Optional[uuid.UUID] = None,
        search: Optional[str] = None,
    ) -> PaginatedResponse[OfficerDetailResponse]:
        """List Area Officers with their assigned geographical areas and pagination."""
        query = select(User).where(User.role == UserRole.AREA_OFFICER)
        count_query = (
            select(func.count(User.id.distinct()))
            .select_from(User)
            .where(User.role == UserRole.AREA_OFFICER)
        )

        if is_active is not None:
            query = query.where(User.is_active == is_active)
            count_query = count_query.where(User.is_active == is_active)

        if area_id is not None:
            query = query.join(AreaOfficerAssignment, User.id == AreaOfficerAssignment.officer_id).where(
                AreaOfficerAssignment.area_id == area_id
            )
            count_query = count_query.join(
                AreaOfficerAssignment, User.id == AreaOfficerAssignment.officer_id
            ).where(AreaOfficerAssignment.area_id == area_id)

        if search:
            pattern = f"%{search.strip()}%"
            search_clause = or_(
                User.full_name.ilike(pattern),
                User.email.ilike(pattern),
                User.phone.ilike(pattern),
            )
            query = query.where(search_clause)
            count_query = count_query.where(search_clause)

        total_res = await db.execute(count_query)
        total = total_res.scalar() or 0

        query = (
            query.options(
                selectinload(User.officer_area_assignments).selectinload(
                    AreaOfficerAssignment.area
                )
            )
            .order_by(User.full_name.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        res = await db.execute(query)
        officers = res.scalars().all()

        items = []
        for off in officers:
            areas = [
                AreaResponse.model_validate(assign.area)
                for assign in off.officer_area_assignments
                if assign.area
            ]
            items.append(
                OfficerDetailResponse(
                    id=off.id,
                    full_name=off.full_name,
                    email=off.email,
                    phone=off.phone,
                    role=off.role.value,
                    is_active=off.is_active,
                    is_verified=off.is_verified,
                    created_at=off.created_at,
                    last_login_at=off.last_login_at,
                    areas=areas,
                )
            )

        return PaginatedResponse.create(
            items=items, total=total, page=page, page_size=page_size
        )

    @staticmethod
    async def get_officer(
        db: AsyncSession, officer_id: uuid.UUID
    ) -> OfficerDetailResponse:
        """Retrieve single Area Officer profile with assigned areas."""
        query = (
            select(User)
            .options(
                selectinload(User.officer_area_assignments).selectinload(
                    AreaOfficerAssignment.area
                )
            )
            .where(User.id == officer_id, User.role == UserRole.AREA_OFFICER)
        )
        result = await db.execute(query)
        officer = result.scalar_one_or_none()
        if not officer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Area Officer not found or user is not an Area Officer.",
            )

        areas = [
            AreaResponse.model_validate(assign.area)
            for assign in officer.officer_area_assignments
            if assign.area
        ]
        return OfficerDetailResponse(
            id=officer.id,
            full_name=officer.full_name,
            email=officer.email,
            phone=officer.phone,
            role=officer.role.value,
            is_active=officer.is_active,
            is_verified=officer.is_verified,
            created_at=officer.created_at,
            last_login_at=officer.last_login_at,
            areas=areas,
        )

    @staticmethod
    async def update_officer(
        db: AsyncSession, officer_id: uuid.UUID, data: OfficerUpdate
    ) -> User:
        """Update Area Officer profile or activation status."""
        query = select(User).where(
            User.id == officer_id, User.role == UserRole.AREA_OFFICER
        )
        result = await db.execute(query)
        officer = result.scalar_one_or_none()
        if not officer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Area Officer not found.",
            )

        if data.full_name is not None:
            officer.full_name = data.full_name
        if data.phone is not None:
            officer.phone = data.phone
        if data.is_active is not None:
            officer.is_active = data.is_active
            if data.is_active is False:
                # Revoke refresh tokens on deactivation
                now = datetime.now(timezone.utc)
                await db.execute(
                    update(RefreshToken)
                    .where(
                        RefreshToken.user_id == officer.id,
                        RefreshToken.revoked_at.is_(None),
                    )
                    .values(revoked_at=now)
                )

        officer.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(officer)
        return officer

    @staticmethod
    async def assign_area(
        db: AsyncSession, officer_id: uuid.UUID, area_id: uuid.UUID
    ) -> AreaOfficerAssignment:
        """Assign an Area Officer to an active Geographical Area."""
        # 1. Validate officer
        query = select(User).where(
            User.id == officer_id, User.role == UserRole.AREA_OFFICER
        )
        res = await db.execute(query)
        officer = res.scalar_one_or_none()
        if not officer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Area Officer not found or user is not an Area Officer.",
            )
        if not officer.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot assign an area to a deactivated officer.",
            )

        # 2. Validate area
        area_res = await db.execute(select(Area).where(Area.id == area_id))
        area = area_res.scalar_one_or_none()
        if not area:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Geographical Area not found.",
            )
        if not area.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot assign officer to an inactive area.",
            )

        # 3. Check duplicate assignment
        existing = await db.execute(
            select(AreaOfficerAssignment).where(
                AreaOfficerAssignment.officer_id == officer_id,
                AreaOfficerAssignment.area_id == area_id,
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Officer is already assigned to this area.",
            )

        assignment = AreaOfficerAssignment(
            officer_id=officer_id,
            area_id=area_id,
        )
        db.add(assignment)
        try:
            await db.commit()
            await db.refresh(assignment)
        except IntegrityError:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Officer is already assigned to this area.",
            )
        return assignment

    @staticmethod
    async def remove_area(
        db: AsyncSession, officer_id: uuid.UUID, area_id: uuid.UUID
    ) -> None:
        """Remove an area assignment from an officer."""
        query = select(AreaOfficerAssignment).where(
            AreaOfficerAssignment.officer_id == officer_id,
            AreaOfficerAssignment.area_id == area_id,
        )
        result = await db.execute(query)
        assignment = result.scalar_one_or_none()
        if assignment:
            await db.delete(assignment)
            await db.commit()

    @staticmethod
    async def get_officer_areas(
        db: AsyncSession, officer_id: uuid.UUID
    ) -> Sequence[Area]:
        """Get all active and inactive areas assigned to a specific officer."""
        query = (
            select(Area)
            .join(AreaOfficerAssignment, Area.id == AreaOfficerAssignment.area_id)
            .where(AreaOfficerAssignment.officer_id == officer_id)
            .order_by(Area.name.asc())
        )
        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def demote_officer_to_civilian(
        db: AsyncSession, officer_id: uuid.UUID
    ) -> User:
        """Demote an Area Officer to Civilian role, clearing all area assignments and revoking tokens."""
        query = select(User).where(
            User.id == officer_id, User.role == UserRole.AREA_OFFICER
        )
        result = await db.execute(query)
        officer = result.scalar_one_or_none()
        if not officer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Area Officer not found.",
            )

        # 1. Remove all officer-area assignments
        await db.execute(
            delete(AreaOfficerAssignment).where(
                AreaOfficerAssignment.officer_id == officer_id
            )
        )

        # 2. Revoke all active refresh tokens for this user
        now = datetime.now(timezone.utc)
        await db.execute(
            update(RefreshToken)
            .where(
                RefreshToken.user_id == officer_id,
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )

        # 3. Demote role to CIVILIAN
        officer.role = UserRole.CIVILIAN
        officer.updated_at = now

        await db.commit()
        await db.refresh(officer)
        return officer
