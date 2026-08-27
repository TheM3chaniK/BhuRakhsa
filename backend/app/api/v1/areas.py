from typing import List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, require_role, verify_area_access
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.area import AreaCreate, AreaResponse, AreaUpdate
from app.schemas.pagination import PaginatedResponse
from app.services.area_service import AreaService

router = APIRouter(prefix="/areas", tags=["Areas"])


@router.get(
    "/active",
    response_model=List[AreaResponse],
    status_code=status.HTTP_200_OK,
    summary="List Active Geographical Areas",
    description="Retrieve all active geographical revenue districts for property deed submissions.",
)
async def list_active_areas(
    db: AsyncSession = Depends(get_db),
) -> List[AreaResponse]:
    """List active geographical areas for public / civilian deed submission."""
    paginated = await AreaService.list_areas(
        db=db, page=1, page_size=100, is_active=True
    )
    return paginated.items


@router.get(
    "",
    response_model=PaginatedResponse[AreaResponse],
    status_code=status.HTTP_200_OK,
    summary="List Geographical Areas",
    description="List administrative areas with pagination and search (Super Admin & Area Officer only). Civilians are forbidden.",
)
async def list_areas(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size limit"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    search: Optional[str] = Query(None, description="Search by area name, code, or description"),
    current_user: User = Depends(
        require_role(UserRole.SUPER_ADMIN, UserRole.AREA_OFFICER)
    ),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[AreaResponse]:
    """List all registered geographical areas with pagination."""
    return await AreaService.list_areas(
        db=db,
        page=page,
        page_size=page_size,
        is_active=is_active,
        search=search,
    )


@router.get(
    "/{area_id}",
    response_model=AreaResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Area by ID",
    description="Retrieve area details. Allowed for Super Admin and assigned Area Officers.",
)
async def get_area(
    area_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AreaResponse:
    """Retrieve details of a single area with strict authorization checks."""
    await verify_area_access(area_id, current_user, db)

    area = await AreaService.get_area(db, area_id)
    if not area:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Area not found.",
        )
    return AreaResponse.model_validate(area)


@router.post(
    "",
    response_model=AreaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Geographical Area",
    description="Provision a new administrative area (Super Admin only).",
)
async def create_area(
    data: AreaCreate,
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> AreaResponse:
    """Create a new geographical area."""
    area = await AreaService.create_area(db, data)
    return AreaResponse.model_validate(area)


@router.patch(
    "/{area_id}",
    response_model=AreaResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Geographical Area",
    description="Update area properties (Super Admin only).",
)
async def update_area(
    area_id: uuid.UUID,
    data: AreaUpdate,
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> AreaResponse:
    """Update an existing geographical area."""
    area = await AreaService.update_area(db, area_id, data)
    return AreaResponse.model_validate(area)


@router.delete(
    "/{area_id}",
    response_model=AreaResponse,
    status_code=status.HTTP_200_OK,
    summary="Deactivate Geographical Area",
    description="Soft delete / deactivate an area (Super Admin only).",
)
async def delete_area(
    area_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> AreaResponse:
    """Soft delete / deactivate an area."""
    area = await AreaService.deactivate_area(db, area_id)
    return AreaResponse.model_validate(area)
