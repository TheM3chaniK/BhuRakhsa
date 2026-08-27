from datetime import datetime, timezone
from typing import Optional, Sequence
import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.models.enums import UserRole
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.pagination import PaginatedResponse
from app.schemas.user import AdminUserUpdate, UserProfileUpdate, UserResponse


class UserService:
    """Service providing civilian account management and administrative user operations."""

    @staticmethod
    async def update_profile(
        db: AsyncSession, user: User, data: UserProfileUpdate
    ) -> User:
        """Update authenticated user's own profile (full_name, phone)."""
        if data.full_name is not None:
            user.full_name = data.full_name
        if data.phone is not None:
            user.phone = data.phone

        user.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(user)
        return user

    @staticmethod
    async def change_password(
        db: AsyncSession, user: User, current_password: str, new_password: str
    ) -> None:
        """Verify current password, update to new password hash, and revoke active refresh tokens."""
        if not verify_password(current_password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Current password is incorrect.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Update password hash
        user.password_hash = hash_password(new_password)
        user.updated_at = datetime.now(timezone.utc)

        # Invalidate all active refresh tokens for this user
        now = datetime.now(timezone.utc)
        await db.execute(
            update(RefreshToken)
            .where(
                RefreshToken.user_id == user.id,
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )

        await db.commit()
        await db.refresh(user)

    @staticmethod
    async def list_users(
        db: AsyncSession,
        page: int = 1,
        page_size: int = 20,
        role: Optional[UserRole] = None,
        is_active: Optional[bool] = None,
        is_verified: Optional[bool] = None,
        search: Optional[str] = None,
    ) -> PaginatedResponse[UserResponse]:
        """List users with pagination, filters, and text search (Super Admin only)."""
        query = select(User)
        count_query = select(func.count()).select_from(User)

        # Apply role filter
        if role is not None:
            query = query.where(User.role == role)
            count_query = count_query.where(User.role == role)

        # Apply is_active filter
        if is_active is not None:
            query = query.where(User.is_active == is_active)
            count_query = count_query.where(User.is_active == is_active)

        # Apply is_verified filter
        if is_verified is not None:
            query = query.where(User.is_verified == is_verified)
            count_query = count_query.where(User.is_verified == is_verified)

        # Apply text search filter
        if search:
            pattern = f"%{search.strip()}%"
            search_clause = or_(
                User.full_name.ilike(pattern),
                User.email.ilike(pattern),
                User.phone.ilike(pattern),
            )
            query = query.where(search_clause)
            count_query = count_query.where(search_clause)

        # Total count
        total_res = await db.execute(count_query)
        total = total_res.scalar() or 0

        # Paginated fetch
        query = (
            query.order_by(User.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        res = await db.execute(query)
        users = res.scalars().all()

        items = [UserResponse.model_validate(u) for u in users]
        return PaginatedResponse.create(
            items=items, total=total, page=page, page_size=page_size
        )

    @staticmethod
    async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User:
        """Fetch user by UUID or raise 404."""
        query = select(User).where(User.id == user_id)
        result = await db.execute(query)
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found.",
            )
        return user

    @staticmethod
    async def update_user_admin(
        db: AsyncSession, user_id: uuid.UUID, data: AdminUserUpdate
    ) -> User:
        """Super Admin update user details and status (with protection for last Super Admin)."""
        user = await UserService.get_user_by_id(db, user_id)

        # Protect against deactivating the last active Super Admin
        if data.is_active is False and user.role == UserRole.SUPER_ADMIN and user.is_active:
            count_res = await db.execute(
                select(func.count()).select_from(User).where(
                    User.role == UserRole.SUPER_ADMIN,
                    User.is_active.is_(True),
                )
            )
            active_admins = count_res.scalar() or 0
            if active_admins <= 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot deactivate the last active Super Admin.",
                )

        if data.full_name is not None:
            user.full_name = data.full_name
        if data.phone is not None:
            user.phone = data.phone
        if data.is_active is not None:
            user.is_active = data.is_active
            # If deactivated, revoke active refresh tokens
            if data.is_active is False:
                now = datetime.now(timezone.utc)
                await db.execute(
                    update(RefreshToken)
                    .where(
                        RefreshToken.user_id == user.id,
                        RefreshToken.revoked_at.is_(None),
                    )
                    .values(revoked_at=now)
                )

        user.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(user)
        return user

    @staticmethod
    async def promote_civilian_to_officer(
        db: AsyncSession, user_id: uuid.UUID
    ) -> User:
        """Promote an existing active civilian user to Area Officer role."""
        user = await UserService.get_user_by_id(db, user_id)

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot promote a deactivated user account.",
            )

        if user.role == UserRole.SUPER_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is already a Super Admin.",
            )

        if user.role == UserRole.AREA_OFFICER:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is already an Area Officer.",
            )

        user.role = UserRole.AREA_OFFICER
        user.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(user)
        return user
