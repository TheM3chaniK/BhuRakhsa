from datetime import datetime
from typing import Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_role
from app.db.session import get_db
from app.models.enums import CaseStatus, RiskLevel, UserRole
from app.models.user import User
from app.schemas.admin_dashboard import OfficerDashboardResponse
from app.schemas.area import AreaResponse, OfficerAreaListResponse
from app.schemas.case import CaseResponse
from app.schemas.pagination import PaginatedResponse
from app.services.officer_dashboard_service import OfficerDashboardService
from app.services.officer_service import OfficerService

router = APIRouter(prefix="/officer", tags=["Officer"])


@router.get(
    "/dashboard",
    response_model=OfficerDashboardResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Area Officer Dashboard",
    description="Retrieve live workload and case distribution scoped strictly to the calling officer's assigned areas.",
)
async def get_officer_dashboard(
    current_user: User = Depends(require_role(UserRole.AREA_OFFICER)),
    db: AsyncSession = Depends(get_db),
) -> OfficerDashboardResponse:
    """Return dashboard metrics for the authenticated officer's jurisdiction."""
    return await OfficerDashboardService.get_officer_dashboard(db, current_user.id)


@router.get(
    "/cases",
    response_model=PaginatedResponse[CaseResponse],
    status_code=status.HTTP_200_OK,
    summary="Search Jurisdiction Cases (Area Officer)",
    description="Search cases strictly scoped to the officer's assigned areas. Frontend area overrides are ignored.",
)
async def search_officer_cases(
    case_id: Optional[uuid.UUID] = Query(None, description="Exact case UUID"),
    case_status: Optional[CaseStatus] = Query(None, alias="status", description="Filter by case status"),
    risk_level: Optional[RiskLevel] = Query(None, description="Filter by risk tier"),
    created_from: Optional[datetime] = Query(None, description="Filter creation starting timestamp"),
    created_to: Optional[datetime] = Query(None, description="Filter creation ending timestamp"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size limit"),
    sort_by: str = Query("created_at", description="Sort field ('created_at', 'updated_at', 'status', 'risk_level')"),
    sort_order: str = Query("desc", description="Sort direction ('asc', 'desc')"),
    current_user: User = Depends(require_role(UserRole.AREA_OFFICER)),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[CaseResponse]:
    """Search cases in officer's assigned areas."""
    if sort_by not in ("created_at", "updated_at", "status", "risk_level"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid sort_by column '{sort_by}'. Allowed: created_at, updated_at, status, risk_level.",
        )
    return await OfficerDashboardService.search_officer_cases(
        db=db,
        officer_id=current_user.id,
        case_id=case_id,
        case_status=case_status,
        risk_level=risk_level,
        created_from=created_from,
        created_to=created_to,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.get(
    "/areas",
    response_model=OfficerAreaListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Assigned Areas for Current Officer",
    description="Retrieve all geographical areas assigned to the authenticated Area Officer.",
)
async def get_my_assigned_areas(
    current_user: User = Depends(require_role(UserRole.AREA_OFFICER)),
    db: AsyncSession = Depends(get_db),
) -> OfficerAreaListResponse:
    """Retrieve areas assigned to the calling officer."""
    areas = await OfficerService.get_officer_areas(db, current_user.id)
    return OfficerAreaListResponse(
        areas=[AreaResponse.model_validate(area) for area in areas]
    )
