from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.admin_dashboard import AdminDashboardResponse
from app.services.admin_dashboard_service import AdminDashboardService

router = APIRouter(tags=["Admin Dashboard"])


@router.get(
    "/dashboard",
    response_model=AdminDashboardResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Super Admin Dashboard Metrics",
    description="Retrieve consolidated system metrics using single-pass SQL aggregations across areas, users, cases, risk, and processing.",
)
async def get_admin_dashboard(
    db: AsyncSession = Depends(get_db),
) -> AdminDashboardResponse:
    """Return consolidated system metrics."""
    return await AdminDashboardService.get_admin_dashboard(db)
