from typing import Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.area import AreaCreate, AreaResponse, AreaUpdate
from app.schemas.pagination import PaginatedResponse
from app.services.area_service import AreaService

router = APIRouter(prefix="/areas", tags=["Admin Areas"])


@router.get(
    "",
    response_model=PaginatedResponse[AreaResponse],
    status_code=status.HTTP_200_OK,
    summary="List Geographical Areas (Super Admin)",
    description="List administrative areas with pagination, active filter, and search (Super Admin only).",
)
async def list_admin_areas(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size limit"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    search: Optional[str] = Query(None, description="Search by area name, code, or description"),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[AreaResponse]:
    """List areas with pagination and search."""
    return await AreaService.list_areas(
        db=db,
        page=page,
        page_size=page_size,
        is_active=is_active,
        search=search,
    )


@router.post(
    "",
    response_model=AreaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Geographical Area",
    description="Provision a new administrative area with unique code (Super Admin only).",
)
async def create_admin_area(
    data: AreaCreate,
    db: AsyncSession = Depends(get_db),
) -> AreaResponse:
    """Create a new geographical area."""
    area = await AreaService.create_area(db, data)
    return AreaResponse.model_validate(area)


@router.get(
    "/{area_id}",
    response_model=AreaResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Area Details (Super Admin)",
    description="Retrieve details of a single geographical area (Super Admin only).",
)
async def get_admin_area(
    area_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> AreaResponse:
    """Retrieve area details."""
    area = await AreaService.get_area(db, area_id)
    if not area:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Geographical Area not found.",
        )
    return AreaResponse.model_validate(area)


@router.patch(
    "/{area_id}",
    response_model=AreaResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Geographical Area",
    description="Update area properties or active status. Deactivating an area with active cases returns 409 Conflict.",
)
async def update_admin_area(
    area_id: uuid.UUID,
    data: AreaUpdate,
    db: AsyncSession = Depends(get_db),
) -> AreaResponse:
    """Update an existing geographical area."""
    area = await AreaService.update_area(db, area_id, data)
    return AreaResponse.model_validate(area)
