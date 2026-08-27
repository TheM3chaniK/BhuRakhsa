from fastapi import APIRouter, Depends

from app.api.dependencies import require_role
from app.api.v1.admin.areas import router as areas_router
from app.api.v1.admin.cases import router as cases_router
from app.api.v1.admin.dashboard import router as dashboard_router
from app.api.v1.admin.officers import router as officers_router
from app.api.v1.admin.queues import router as queues_router
from app.api.v1.admin.reference_properties import router as reference_properties_router
from app.api.v1.admin.statistics import router as statistics_router
from app.api.v1.admin.summary import router as summary_router
from app.api.v1.admin.system_health import router as system_health_router
from app.api.v1.admin.users import router as users_router
from app.models.enums import UserRole

admin_router = APIRouter(
    prefix="/admin",
    dependencies=[Depends(require_role(UserRole.SUPER_ADMIN))],
)

admin_router.include_router(dashboard_router)
admin_router.include_router(users_router)
admin_router.include_router(officers_router)
admin_router.include_router(areas_router)
admin_router.include_router(cases_router)
admin_router.include_router(statistics_router)
admin_router.include_router(queues_router)
admin_router.include_router(system_health_router)
admin_router.include_router(reference_properties_router)
admin_router.include_router(summary_router)

__all__ = ["admin_router"]
