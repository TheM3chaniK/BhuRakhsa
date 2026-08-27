from datetime import datetime
from typing import Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.enums import CaseStatus, RiskLevel
from app.schemas.admin_dashboard import AdminCaseDetailResponse
from app.schemas.case import CaseResponse
from app.schemas.pagination import PaginatedResponse
from app.services.admin_dashboard_service import AdminDashboardService

router = APIRouter(prefix="/cases", tags=["Admin Cases"])


@router.get(
    "",
    response_model=PaginatedResponse[CaseResponse],
    status_code=status.HTTP_200_OK,
    summary="Search All Cases (Super Admin)",
    description="Search cases across all areas with flexible query filters (Super Admin only).",
)
async def search_cases(
    case_id: Optional[uuid.UUID] = Query(None, description="Exact case UUID"),
    area_id: Optional[uuid.UUID] = Query(None, description="Geographical Area UUID"),
    case_status: Optional[CaseStatus] = Query(None, alias="status", description="Filter by case status"),
    risk_level: Optional[RiskLevel] = Query(None, description="Filter by risk tier"),
    created_from: Optional[datetime] = Query(None, description="Filter creation starting timestamp"),
    created_to: Optional[datetime] = Query(None, description="Filter creation ending timestamp"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size limit"),
    sort_by: str = Query("created_at", description="Sort field ('created_at', 'updated_at', 'status', 'risk_level')"),
    sort_order: str = Query("desc", description="Sort direction ('asc', 'desc')"),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[CaseResponse]:
    """Search cases with authorization-safe pagination and filters."""
    if sort_by not in ("created_at", "updated_at", "status", "risk_level"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid sort_by column '{sort_by}'. Allowed: created_at, updated_at, status, risk_level.",
        )
    return await AdminDashboardService.search_cases(
        db=db,
        case_id=case_id,
        area_id=area_id,
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
    "/{case_id}",
    response_model=AdminCaseDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get 360-Degree Case Operational Detail",
    description="Retrieve the complete operational dossier of a case across all intelligence layers (Super Admin only).",
)
async def get_admin_case_detail(
    case_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> AdminCaseDetailResponse:
    """Retrieve full operational dossier for a case."""
    return await AdminDashboardService.get_admin_case_detail(db, case_id)
