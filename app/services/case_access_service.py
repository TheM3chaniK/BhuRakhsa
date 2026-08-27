from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.area_officer_assignment import AreaOfficerAssignment
from app.models.case import Case
from app.models.enums import UserRole
from app.models.user import User


class CaseAccessService:
    """Service evaluating authoritative access permissions on Case entities."""

    @staticmethod
    async def can_access_case(db: AsyncSession, user: User, case: Case) -> bool:
        """Evaluate if the user has read/access rights for the given case.

        Rules:
        - SUPER_ADMIN: Unrestricted access across all cases.
        - CIVILIAN: Only cases created by the civilian user.
        - AREA_OFFICER: Only cases whose area is assigned to the officer.
        """
        if user.role == UserRole.SUPER_ADMIN:
            return True

        if user.role == UserRole.CIVILIAN:
            return case.created_by == user.id

        if user.role == UserRole.AREA_OFFICER:
            query = select(AreaOfficerAssignment).where(
                AreaOfficerAssignment.officer_id == user.id,
                AreaOfficerAssignment.area_id == case.area_id,
            )
            result = await db.execute(query)
            return result.scalar_one_or_none() is not None

        return False

    @staticmethod
    async def verify_case_access(db: AsyncSession, user: User, case: Case) -> None:
        """Verify case access or raise HTTP 403 Forbidden."""
        has_access = await CaseAccessService.can_access_case(db, user, case)
        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this case.",
            )
