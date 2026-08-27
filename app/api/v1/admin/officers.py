from typing import List, Optional
import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.area import AreaResponse
from app.schemas.officer import (
    ActionSuccessResponse,
    AssignmentActionResponse,
    OfficerCreate,
    OfficerDetailResponse,
    OfficerUpdate,
)
from app.schemas.pagination import PaginatedResponse
from app.schemas.user import UserResponse
from app.services.officer_service import OfficerService

router = APIRouter(prefix="/officers", tags=["Admin Officers"])


@router.get(
    "",
    response_model=PaginatedResponse[OfficerDetailResponse],
    status_code=status.HTTP_200_OK,
    summary="List Area Officers",
    description="List all Area Officers with their assigned geographical areas (Super Admin only).",
)
async def list_officers(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size limit"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    area_id: Optional[uuid.UUID] = Query(None, description="Filter by assigned area UUID"),
    search: Optional[str] = Query(None, description="Search by name, email, or phone"),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[OfficerDetailResponse]:
    """List Area Officers with assigned areas."""
    return await OfficerService.list_officers(
        db=db,
        page=page,
        page_size=page_size,
        is_active=is_active,
        area_id=area_id,
        search=search,
    )


@router.get(
    "/{officer_id}",
    response_model=OfficerDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Area Officer Profile",
    description="Retrieve Area Officer details and assigned areas (Super Admin only).",
)
async def get_officer(
    officer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> OfficerDetailResponse:
    """Retrieve single Area Officer profile."""
    return await OfficerService.get_officer(db, officer_id)


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Area Officer",
    description="Provision a new Area Officer account (Super Admin only). Role is forced to AREA_OFFICER.",
)
async def create_officer(
    data: OfficerCreate,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Create a new Area Officer account."""
    officer = await OfficerService.create_officer(db, data)
    return UserResponse.model_validate(officer)


@router.patch(
    "/{officer_id}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Area Officer Profile / Status",
    description="Update officer details or activate/deactivate account (Super Admin only).",
)
async def update_officer(
    officer_id: uuid.UUID,
    data: OfficerUpdate,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Update officer profile or status."""
    officer = await OfficerService.update_officer(db, officer_id, data)
    return UserResponse.model_validate(officer)


@router.post(
    "/{officer_id}/areas/{area_id}",
    response_model=AssignmentActionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Assign Officer to Area",
    description="Assign an Area Officer to an active geographical area (Super Admin only).",
)
async def assign_officer_to_area(
    officer_id: uuid.UUID,
    area_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> AssignmentActionResponse:
    """Assign an officer to an active area."""
    assignment = await OfficerService.assign_area(db, officer_id, area_id)
    return AssignmentActionResponse(
        success=True,
        officer_id=assignment.officer_id,
        area_id=assignment.area_id,
        message="Officer assigned to area successfully.",
    )


@router.delete(
    "/{officer_id}/areas/{area_id}",
    response_model=ActionSuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Remove Officer Area Assignment",
    description="Unassign an officer from a geographical area (Super Admin only).",
)
async def remove_officer_from_area(
    officer_id: uuid.UUID,
    area_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ActionSuccessResponse:
    """Remove an officer's area assignment."""
    await OfficerService.remove_area(db, officer_id, area_id)
    return ActionSuccessResponse(
        success=True,
        message="Officer removed from area successfully.",
    )


@router.get(
    "/{officer_id}/areas",
    response_model=List[AreaResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Officer Assigned Areas",
    description="List all areas assigned to a specific officer (Super Admin only).",
)
async def get_officer_assigned_areas(
    officer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> List[AreaResponse]:
    """List areas assigned to a given officer."""
    areas = await OfficerService.get_officer_areas(db, officer_id)
    return [AreaResponse.model_validate(a) for a in areas]


@router.post(
    "/{officer_id}/demote",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Demote Area Officer to Civilian",
    description="Demote an Area Officer to Civilian, clearing all area assignments and revoking tokens (Super Admin only).",
)
async def demote_officer(
    officer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Demote Area Officer to Civilian."""
    user = await OfficerService.demote_officer_to_civilian(db, officer_id)
    return UserResponse.model_validate(user)
