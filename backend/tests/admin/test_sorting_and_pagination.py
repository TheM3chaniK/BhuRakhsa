from unittest.mock import AsyncMock, patch
import uuid
from httpx import ASGITransport, AsyncClient
import pytest

from app.api.dependencies import get_current_user
from app.main import app
from app.models.user import User
from app.schemas.pagination import PaginatedResponse
from app.services.admin_dashboard_service import AdminDashboardService


@pytest.mark.anyio
async def test_sorting_and_pagination_validation(super_admin_user: User) -> None:
    """Verify sorting allowlist and pagination bounding parameters."""
    app.dependency_overrides[get_current_user] = lambda: super_admin_user
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Invalid sort column -> 400 Bad Request
        res_invalid_sort = await ac.get("/api/v1/admin/cases?sort_by=malicious_sql_column")
        assert res_invalid_sort.status_code == 400
        assert "Invalid sort_by column" in res_invalid_sort.json()["detail"]

        # 2. page_size > 100 -> 422 Unprocessable Entity
        res_large_page = await ac.get("/api/v1/admin/cases?page_size=500")
        assert res_large_page.status_code == 422

        # 3. page < 1 -> 422 Unprocessable Entity
        res_zero_page = await ac.get("/api/v1/admin/cases?page=0")
        assert res_zero_page.status_code == 422

        # 4. Valid sort columns
        with patch.object(
            AdminDashboardService, "search_cases", new_callable=AsyncMock
        ) as mock_search:
            mock_search.return_value = PaginatedResponse.create(items=[], total=0, page=1, page_size=20)

            for col in ["created_at", "updated_at", "status", "risk_level"]:
                res_ok = await ac.get(f"/api/v1/admin/cases?sort_by={col}&sort_order=asc")
                assert res_ok.status_code == 200

    app.dependency_overrides.clear()
