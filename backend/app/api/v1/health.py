from fastapi import APIRouter, Response, status

from app.core.config import settings
from app.schemas.health import DatabaseHealth, DetailedHealthResponse
from app.services.database_health_service import DatabaseHealthService
from app.services.ollama_service import OllamaService

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=DetailedHealthResponse,
    summary="API v1 Health Check",
    description="Check the operational status of the v1 API, database/PostGIS, and Ollama connection.",
)
async def get_v1_health(response: Response) -> DetailedHealthResponse:
    """Return health status of the v1 API and connected infrastructure."""
    db_health = await DatabaseHealthService.check_engine_health()
    ollama_ok = await OllamaService().check_connection()

    db_model = DatabaseHealth(
        status=db_health["status"],
        postgresql=db_health["postgresql"],
        postgis=db_health["postgis"],
    )

    overall_status = "ok" if db_health["status"] == "ok" else "degraded"
    if overall_status != "ok":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return DetailedHealthResponse(
        status=overall_status,
        service="property-document-verification-api",
        version=settings.APP_VERSION,
        database=db_model,
        ollama=ollama_ok,
    )
