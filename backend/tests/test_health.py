from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from app.main import app

client = TestClient(app)


def test_root_health_endpoint() -> None:
    """Verify that GET /health returns 200 and expected health metadata via TestClient."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "property-document-verification-api"
    assert data["version"] == "0.1.0"


@pytest.mark.anyio
async def test_async_root_health_endpoint() -> None:
    """Verify async request to GET /health via HTTPX AsyncClient."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "property-document-verification-api"
        assert data["version"] == "0.1.0"


@pytest.mark.anyio
async def test_api_v1_health_healthy() -> None:
    """Verify that GET /api/v1/health returns 200 when database and postgis are healthy."""
    mock_health = {"status": "ok", "postgresql": True, "postgis": True}
    with patch(
        "app.services.database_health_service.DatabaseHealthService.check_engine_health",
        new_callable=AsyncMock,
        return_value=mock_health,
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.get("/api/v1/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"
            assert data["service"] == "property-document-verification-api"
            assert data["version"] == "0.1.0"
            assert data["database"]["status"] == "ok"
            assert data["database"]["postgresql"] is True
            assert data["database"]["postgis"] is True


@pytest.mark.anyio
async def test_api_v1_health_unhealthy() -> None:
    """Verify that GET /api/v1/health returns 503 when database is unreachable."""
    mock_unhealthy = {"status": "unhealthy", "postgresql": False, "postgis": False}
    with patch(
        "app.services.database_health_service.DatabaseHealthService.check_engine_health",
        new_callable=AsyncMock,
        return_value=mock_unhealthy,
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.get("/api/v1/health")
            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "degraded"
            assert data["database"]["status"] == "unhealthy"
            assert data["database"]["postgresql"] is False
            assert data["database"]["postgis"] is False
