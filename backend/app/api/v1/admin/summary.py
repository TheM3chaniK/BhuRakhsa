from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.admin import AdminSummaryResponse
from app.services.area_service import AreaService

router = APIRouter(prefix="/summary", tags=["Admin Summary"])


@router.get(
    "",
    response_model=AdminSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Administrative Summary Metrics",
    description="Retrieve aggregate counts across users, geographical areas, and officer assignments (Super Admin only).",
)
async def get_admin_summary(
    db: AsyncSession = Depends(get_db),
) -> AdminSummaryResponse:
    """Return dashboard summary metrics."""
    return await AreaService.get_admin_summary(db)
