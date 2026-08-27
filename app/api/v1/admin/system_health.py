from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.admin_dashboard import AdminSystemHealthResponse
from app.services.admin_dashboard_service import AdminDashboardService

router = APIRouter(prefix="/system", tags=["Admin System Health"])


@router.get(
    "/health",
    response_model=AdminSystemHealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Detailed System Health",
    description="Comprehensive health inspection across PostgreSQL, PostGIS, Object Storage, Ollama, DeepSeek OCR, and background workers (Super Admin only).",
)
async def get_system_health(
    db: AsyncSession = Depends(get_db),
) -> AdminSystemHealthResponse:
    """Return detailed system health analysis."""
    return await AdminDashboardService.get_detailed_system_health(db)
