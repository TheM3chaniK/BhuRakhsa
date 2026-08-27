from typing import Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, require_role
from app.db.session import get_db
from app.models.enums import CaseStatus, RiskLevel, UserRole
from app.models.user import User
from app.schemas.case import (
    CaseCreate,
    CaseResponse,
    CaseSubmissionResponse,
    CaseUpdate,
)
from app.schemas.final_decision import CivilianCaseStatusResponse
from app.schemas.pagination import PaginatedResponse
from app.services.case_access_service import CaseAccessService
from app.services.case_service import CaseService

router = APIRouter(prefix="/cases", tags=["Cases"])


@router.post(
    "",
    response_model=CaseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Verification Case",
    description="Create a new property verification case in DRAFT status (Civilian only).",
)
async def create_case(
    data: CaseCreate,
    current_user: User = Depends(require_role(UserRole.CIVILIAN)),
    db: AsyncSession = Depends(get_db),
) -> CaseResponse:
    """Create a new case belonging to the authenticated civilian."""
    new_case = await CaseService.create_case(db, current_user, data)
    return CaseResponse.model_validate(new_case)


@router.get(
    "",
    response_model=PaginatedResponse[CaseResponse],
    status_code=status.HTTP_200_OK,
    summary="List Cases",
    description="List cases scoped by role: Civilians see only own cases, Area Officers see cases in assigned areas, Super Admin sees all.",
)
async def list_cases(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size limit"),
    case_status: Optional[CaseStatus] = Query(None, alias="status", description="Filter by case status"),
    risk_level: Optional[RiskLevel] = Query(None, description="Filter by risk level"),
    area_id: Optional[uuid.UUID] = Query(None, description="Filter by area UUID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[CaseResponse]:
    """Retrieve paginated case list scoped by role."""
    return await CaseService.list_cases(
        db=db,
        user=current_user,
        page=page,
        page_size=page_size,
        case_status=case_status,
        risk_level=risk_level,
        area_id=area_id,
    )


@router.get(
    "/{case_id}",
    response_model=CaseResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Case Details",
    description="Retrieve details of a single case. Requires case ownership (Civilian), jurisdictional assignment (Officer), or Admin role.",
)
async def get_case(
    case_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CaseResponse:
    """Retrieve case with strict role and jurisdiction authorization checks."""
    case = await CaseService.get_case(db, case_id)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Case not found.",
        )

    await CaseAccessService.verify_case_access(db, current_user, case)
    return CaseResponse.model_validate(case)


@router.get(
    "/{case_id}/status",
    response_model=CivilianCaseStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Simplified Case Status",
    description="Retrieve simplified case status milestone without internal risk or officer notes.",
)
async def get_case_status(
    case_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CivilianCaseStatusResponse:
    """Retrieve simplified case status view."""
    case = await CaseService.get_case(db, case_id)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Case not found.",
        )
    await CaseAccessService.verify_case_access(db, current_user, case)
    return CivilianCaseStatusResponse(
        case_id=case.id,
        status=case.status,
        updated_at=case.updated_at,
        title=case.title,
    )


@router.patch(
    "/{case_id}",
    response_model=CaseResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Draft Case",
    description="Update basic property information and area for a case in DRAFT status (Civilian owner only).",
)
async def update_case(
    case_id: uuid.UUID,
    data: CaseUpdate,
    current_user: User = Depends(require_role(UserRole.CIVILIAN)),
    db: AsyncSession = Depends(get_db),
) -> CaseResponse:
    """Update allowed fields of a draft case."""
    updated_case = await CaseService.update_case(db, case_id, current_user, data)
    return CaseResponse.model_validate(updated_case)


@router.post(
    "/{case_id}/submit",
    response_model=CaseSubmissionResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit Verification Case",
    description="Transition case from DRAFT to SUBMITTED status (Civilian owner only).",
)
async def submit_case(
    case_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.CIVILIAN)),
    db: AsyncSession = Depends(get_db),
) -> CaseSubmissionResponse:
    """Submit a draft case for verification."""
    submitted_case = await CaseService.submit_case(db, case_id, current_user)
    return CaseSubmissionResponse.model_validate(submitted_case)
