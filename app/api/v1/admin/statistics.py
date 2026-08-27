from datetime import datetime
from typing import Optional
import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.admin_dashboard import (
    CaseStatisticsResponse,
    OfficerStatisticsResponse,
    ProcessingStatisticsResponse,
    ProofStatisticsResponse,
    ReviewStatisticsResponse,
    RiskStatisticsResponse,
)
from app.services.admin_dashboard_service import AdminDashboardService

router = APIRouter(prefix="/statistics", tags=["Admin Statistics"])


@router.get(
    "/cases",
    response_model=CaseStatisticsResponse,
    status_code=status.HTTP_200_OK,
    summary="Case Statistics",
    description="Retrieve aggregated case statistics by status and area.",
)
async def get_case_statistics(
    area_id: Optional[uuid.UUID] = Query(None, description="Optional area filter"),
    from_date: Optional[datetime] = Query(None, alias="from", description="Start datetime filter"),
    to_date: Optional[datetime] = Query(None, alias="to", description="End datetime filter"),
    db: AsyncSession = Depends(get_db),
) -> CaseStatisticsResponse:
    """Return aggregated case metrics."""
    return await AdminDashboardService.get_case_statistics(db, area_id, from_date, to_date)


@router.get(
    "/risk",
    response_model=RiskStatisticsResponse,
    status_code=status.HTTP_200_OK,
    summary="Risk Statistics",
    description="Retrieve aggregated risk level distributions and average risk scores.",
)
async def get_risk_statistics(
    area_id: Optional[uuid.UUID] = Query(None, description="Optional area filter"),
    from_date: Optional[datetime] = Query(None, alias="from", description="Start datetime filter"),
    to_date: Optional[datetime] = Query(None, alias="to", description="End datetime filter"),
    db: AsyncSession = Depends(get_db),
) -> RiskStatisticsResponse:
    """Return aggregated risk metrics."""
    return await AdminDashboardService.get_risk_statistics(db, area_id, from_date, to_date)


@router.get(
    "/reviews",
    response_model=ReviewStatisticsResponse,
    status_code=status.HTTP_200_OK,
    summary="Review Statistics",
    description="Retrieve review completion metrics and decision distributions.",
)
async def get_review_statistics(
    area_id: Optional[uuid.UUID] = Query(None, description="Optional area filter"),
    from_date: Optional[datetime] = Query(None, alias="from", description="Start datetime filter"),
    to_date: Optional[datetime] = Query(None, alias="to", description="End datetime filter"),
    db: AsyncSession = Depends(get_db),
) -> ReviewStatisticsResponse:
    """Return aggregated review metrics."""
    return await AdminDashboardService.get_review_statistics(db, area_id, from_date, to_date)


@router.get(
    "/proofs",
    response_model=ProofStatisticsResponse,
    status_code=status.HTTP_200_OK,
    summary="Proof Statistics",
    description="Retrieve supplementary proof request metrics.",
)
async def get_proof_statistics(
    area_id: Optional[uuid.UUID] = Query(None, description="Optional area filter"),
    from_date: Optional[datetime] = Query(None, alias="from", description="Start datetime filter"),
    to_date: Optional[datetime] = Query(None, alias="to", description="End datetime filter"),
    db: AsyncSession = Depends(get_db),
) -> ProofStatisticsResponse:
    """Return aggregated proof request metrics."""
    return await AdminDashboardService.get_proof_statistics(db, area_id, from_date, to_date)


@router.get(
    "/processing",
    response_model=ProcessingStatisticsResponse,
    status_code=status.HTTP_200_OK,
    summary="Processing Statistics",
    description="Retrieve document processing, OCR, and background job success rates.",
)
async def get_processing_statistics(
    area_id: Optional[uuid.UUID] = Query(None, description="Optional area filter"),
    from_date: Optional[datetime] = Query(None, alias="from", description="Start datetime filter"),
    to_date: Optional[datetime] = Query(None, alias="to", description="End datetime filter"),
    db: AsyncSession = Depends(get_db),
) -> ProcessingStatisticsResponse:
    """Return aggregated processing metrics."""
    return await AdminDashboardService.get_processing_statistics(db, area_id, from_date, to_date)


@router.get(
    "/officers",
    response_model=OfficerStatisticsResponse,
    status_code=status.HTTP_200_OK,
    summary="Officer Statistics",
    description="Retrieve Area Officer assignment statistics and review throughput.",
)
async def get_officer_statistics(
    area_id: Optional[uuid.UUID] = Query(None, description="Optional area filter"),
    from_date: Optional[datetime] = Query(None, alias="from", description="Start datetime filter"),
    to_date: Optional[datetime] = Query(None, alias="to", description="End datetime filter"),
    db: AsyncSession = Depends(get_db),
) -> OfficerStatisticsResponse:
    """Return aggregated officer performance metrics."""
    return await AdminDashboardService.get_officer_statistics(db, area_id, from_date, to_date)
