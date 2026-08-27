from typing import Optional
import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.admin_dashboard import (
    FailedJobListResponse,
    JobRetryResponse,
    QueueMonitoringResponse,
)
from app.services.admin_dashboard_service import AdminDashboardService

router = APIRouter(tags=["Admin Queues & Jobs"])


@router.get(
    "/queues",
    response_model=QueueMonitoringResponse,
    status_code=status.HTTP_200_OK,
    summary="Monitor Queue Depths",
    description="Retrieve live queue depths across OCR, extraction, validation, GIS, revalidation, and outbox queues (Super Admin only).",
)
async def get_queue_monitoring(
    db: AsyncSession = Depends(get_db),
) -> QueueMonitoringResponse:
    """Return queue metrics."""
    return await AdminDashboardService.get_queue_monitoring(db)


@router.get(
    "/jobs/failed",
    response_model=FailedJobListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Failed Background Jobs",
    description="List failed background jobs with sanitized error messages (Super Admin only).",
)
async def list_failed_jobs(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size limit"),
    db: AsyncSession = Depends(get_db),
) -> FailedJobListResponse:
    """List failed jobs."""
    return await AdminDashboardService.get_failed_jobs(db, page, page_size)


@router.post(
    "/jobs/{job_id}/retry",
    response_model=JobRetryResponse,
    status_code=status.HTTP_200_OK,
    summary="Retry Failed Background Job",
    description="Manually reset a failed background job or outbox event to PENDING and record an audit event (Super Admin only).",
)
async def retry_failed_job(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JobRetryResponse:
    """Retry a failed job."""
    return await AdminDashboardService.retry_failed_job(db, job_id, current_user.id)
