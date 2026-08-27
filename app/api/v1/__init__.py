from fastapi import APIRouter

from app.api.v1.admin import admin_router
from app.api.v1.areas import router as areas_router
from app.api.v1.audit import router as audit_router
from app.api.v1.auth import router as auth_router
from app.api.v1.cases import router as cases_router
from app.api.v1.civilian_cases import router as civilian_cases_router
from app.api.v1.documents import router as documents_router
from app.api.v1.final_decision import router as final_decision_router
from app.api.v1.health import router as health_router
from app.api.v1.notifications import router as notifications_router
from app.api.v1.officer import router as officer_router
from app.api.v1.proofs import router as proofs_router
from app.api.v1.property_profiles import router as property_profiles_router
from app.api.v1.reviews import router as reviews_router
from app.api.v1.risk import router as risk_router
from app.api.v1.users import router as users_router

api_v1_router = APIRouter()
api_v1_router.include_router(health_router)
api_v1_router.include_router(auth_router)
api_v1_router.include_router(users_router)
api_v1_router.include_router(areas_router)
api_v1_router.include_router(officer_router)
api_v1_router.include_router(admin_router)
api_v1_router.include_router(cases_router)
api_v1_router.include_router(civilian_cases_router)
api_v1_router.include_router(documents_router)
api_v1_router.include_router(property_profiles_router)
api_v1_router.include_router(risk_router)
api_v1_router.include_router(reviews_router)
api_v1_router.include_router(proofs_router)
api_v1_router.include_router(final_decision_router)
api_v1_router.include_router(audit_router)
api_v1_router.include_router(notifications_router)

__all__ = ["api_v1_router"]
