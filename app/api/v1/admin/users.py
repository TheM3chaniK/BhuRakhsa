from typing import Optional
import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.enums import UserRole
from app.schemas.pagination import PaginatedResponse
from app.schemas.user import AdminUserUpdate, UserResponse
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["Admin Users"])


@router.get(
    "",
    response_model=PaginatedResponse[UserResponse],
    status_code=status.HTTP_200_OK,
    summary="List All Users",
    description="List system users with pagination, role filter, status filter, and text search (Super Admin only).",
)
async def list_users(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size limit"),
    role: Optional[UserRole] = Query(None, description="Filter by user role"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    is_verified: Optional[bool] = Query(None, description="Filter by verification status"),
    search: Optional[str] = Query(None, description="Search by name, email, or phone"),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[UserResponse]:
    """Retrieve paginated user list."""
    return await UserService.list_users(
        db=db,
        page=page,
        page_size=page_size,
        role=role,
        is_active=is_active,
        is_verified=is_verified,
        search=search,
    )


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get User Details",
    description="Retrieve full user account details by UUID (Super Admin only).",
)
async def get_user_details(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Retrieve user details."""
    user = await UserService.get_user_by_id(db, user_id)
    return UserResponse.model_validate(user)


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Update User Profile / Status",
    description="Update user profile attributes or activate/deactivate account (Super Admin only).",
)
async def update_user(
    user_id: uuid.UUID,
    data: AdminUserUpdate,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Update user profile or activation status."""
    user = await UserService.update_user_admin(db, user_id, data)
    return UserResponse.model_validate(user)


@router.post(
    "/{user_id}/promote-to-officer",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Promote Civilian to Area Officer",
    description="Promote an active civilian account to Area Officer role (Super Admin only).",
)
async def promote_to_officer(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Promote civilian to Area Officer."""
    user = await UserService.promote_civilian_to_officer(db, user_id)
    return UserResponse.model_validate(user)
