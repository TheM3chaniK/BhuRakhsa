from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
import uuid
from httpx import ASGITransport, AsyncClient
import pytest

from app.api.dependencies import get_current_user
from app.main import app
from app.models.area import Area
from app.models.user import User
from app.schemas.area import AreaResponse
from app.schemas.pagination import PaginatedResponse
from app.services.area_service import AreaService


@pytest.mark.anyio
async def test_admin_areas_crud_flow(super_admin_user: User) -> None:
    """Verify Super Admin area management CRUD endpoints under /api/v1/admin/areas."""
    area_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    mock_area = Area(
        id=area_id,
        name="Sector 7 Sub-District",
        code="SEC-7",
        description="Administrative sub-district zone 7",
        is_active=True,
        created_at=now,
        updated_at=now,
    )

    with patch.object(AreaService, "create_area", new_callable=AsyncMock) as m_create, \
         patch.object(AreaService, "list_areas", new_callable=AsyncMock) as m_list, \
         patch.object(AreaService, "get_area", new_callable=AsyncMock) as m_get, \
         patch.object(AreaService, "update_area", new_callable=AsyncMock) as m_update:

        m_create.return_value = mock_area
        m_list.return_value = PaginatedResponse.create(
            items=[AreaResponse.model_validate(mock_area)],
            total=1,
            page=1,
            page_size=20,
        )
        m_get.return_value = mock_area
        m_update.return_value = mock_area

        app.dependency_overrides[get_current_user] = lambda: super_admin_user
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            # 1. Create Area -> 201 Created
            res_create = await ac.post(
                "/api/v1/admin/areas",
                json={"name": "Sector 7 Sub-District", "code": "SEC-7", "description": "Administrative sub-district zone 7"},
            )
            assert res_create.status_code == 201
            assert res_create.json()["code"] == "SEC-7"

            # 2. List Areas -> 200 OK
            res_list = await ac.get("/api/v1/admin/areas?page=1&page_size=20")
            assert res_list.status_code == 200
            assert res_list.json()["total"] == 1

            # 3. Get Area -> 200 OK
            res_get = await ac.get(f"/api/v1/admin/areas/{area_id}")
            assert res_get.status_code == 200
            assert res_get.json()["id"] == str(area_id)

            # 4. Patch Area -> 200 OK
            res_patch = await ac.patch(
                f"/api/v1/admin/areas/{area_id}",
                json={"name": "Sector 7 North Sub-District"},
            )
            assert res_patch.status_code == 200

        app.dependency_overrides.clear()
