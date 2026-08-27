from typing import List
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_role
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.area import AreaResponse
from app.schemas.auth import MessageResponse
from app.schemas.officer import (
    OfficerAssignmentResponse,
    OfficerCreate,
    OfficerUpdate,
)
from app.schemas.user import UserResponse
from app.services.area_service import AreaService

router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
    dependencies=[Depends(require_role(UserRole.SUPER_ADMIN))],
)


@router.get(
    "/officers",
    response_model=List[UserResponse],
    status_code=status.HTTP_200_OK,
    summary="List Area Officers",
    description="List all registered Area Officers (Super Admin only).",
)
async def list_officers(
    db: AsyncSession = Depends(get_db),
) -> List[UserResponse]:
    """List all registered Area Officers."""
    officers = await AreaService.list_officers(db)
    return [UserResponse.model_validate(officer) for officer in officers]


@router.get(
    "/officers/{officer_id}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Officer by ID",
    description="Retrieve officer details by UUID (Super Admin only).",
)
async def get_officer(
    officer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Retrieve single Area Officer."""
    officer = await AreaService.get_officer(db, officer_id)
    if not officer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Area Officer not found.",
        )
    return UserResponse.model_validate(officer)


@router.post(
    "/officers",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Area Officer",
    description="Create an Area Officer account (Super Admin only). Role is forced to AREA_OFFICER.",
)
async def create_officer(
    data: OfficerCreate,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Create a new Area Officer."""
    officer = await AreaService.create_officer(db, data)
    return UserResponse.model_validate(officer)


@router.patch(
    "/officers/{officer_id}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Area Officer",
    description="Update profile or activation status for an officer (Super Admin only).",
)
async def update_officer(
    officer_id: uuid.UUID,
    data: OfficerUpdate,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Update officer profile or status."""
    officer = await AreaService.update_officer(db, officer_id, data)
    return UserResponse.model_validate(officer)


@router.post(
    "/officers/{officer_id}/areas/{area_id}",
    response_model=OfficerAssignmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Assign Officer to Area",
    description="Assign an Area Officer to an active Geographical Area (Super Admin only).",
)
async def assign_officer_to_area(
    officer_id: uuid.UUID,
    area_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> OfficerAssignmentResponse:
    """Assign an officer to an area."""
    assignment = await AreaService.assign_officer_to_area(db, officer_id, area_id)
    return OfficerAssignmentResponse.model_validate(assignment)


@router.delete(
    "/officers/{officer_id}/areas/{area_id}",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Remove Officer Area Assignment",
    description="Unassign an officer from a Geographical Area (Super Admin only).",
)
async def remove_officer_from_area(
    officer_id: uuid.UUID,
    area_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Remove an officer's area assignment."""
    await AreaService.remove_officer_from_area(db, officer_id, area_id)
    return MessageResponse(message="Officer successfully unassigned from area.")


@router.get(
    "/officers/{officer_id}/areas",
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
    areas = await AreaService.get_officer_areas(db, officer_id)
    return [AreaResponse.model_validate(area) for area in areas]
