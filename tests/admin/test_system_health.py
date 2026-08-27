from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from httpx import ASGITransport, AsyncClient
import pytest

from app.api.dependencies import get_current_user
from app.main import app
from app.models.user import User
from app.schemas.admin_dashboard import AdminSystemHealthResponse, SystemComponentHealth
from app.services.admin_dashboard_service import AdminDashboardService


@pytest.mark.anyio
async def test_system_health_endpoints(super_admin_user: User, civilian_user: User) -> None:
    """Verify minimal public /health and detailed /api/v1/admin/system/health."""
    now = datetime.now(timezone.utc)
    mock_health = AdminSystemHealthResponse(
        status="healthy",
        components={
            "postgresql": SystemComponentHealth(status="healthy", details={"latency_ms": 1.2}),
            "postgis": SystemComponentHealth(status="healthy"),
            "object_storage": SystemComponentHealth(status="healthy"),
            "ollama": SystemComponentHealth(status="healthy"),
            "deepseek_ocr": SystemComponentHealth(status="healthy"),
            "background_worker": SystemComponentHealth(status="healthy"),
            "outbox_worker": SystemComponentHealth(status="healthy"),
        },
        timestamp=now,
    )

    with patch.object(AdminDashboardService, "get_detailed_system_health", new_callable=AsyncMock) as m_health:
        m_health.return_value = mock_health

        # 1. Public minimal health check (unauthenticated) -> 200 OK
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            res_pub = await ac.get("/health")
            assert res_pub.status_code == 200
            assert res_pub.json()["status"] == "ok"
            # Ensure no credentials or internal hostnames are disclosed
            assert "postgresql" not in res_pub.json()
            assert "ollama" not in res_pub.json()

        # 2. Detailed health check (Super Admin) -> 200 OK
        app.dependency_overrides[get_current_user] = lambda: super_admin_user
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            res_admin = await ac.get("/api/v1/admin/system/health")
            assert res_admin.status_code == 200
            data = res_admin.json()
            assert data["status"] == "healthy"
            assert "postgresql" in data["components"]
            assert "deepseek_ocr" in data["components"]

        # 3. Detailed health check (Civilian) -> 403 Forbidden
        app.dependency_overrides[get_current_user] = lambda: civilian_user
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            res_civ = await ac.get("/api/v1/admin/system/health")
            assert res_civ.status_code == 403

        app.dependency_overrides.clear()
