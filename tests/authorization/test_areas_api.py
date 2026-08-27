from unittest.mock import AsyncMock, patch
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_current_user
from app.main import app
from app.models.area import Area
from app.models.user import User
from app.schemas.area import AreaResponse
from app.schemas.pagination import PaginatedResponse
from app.services.area_service import AreaService


@pytest.mark.anyio
async def test_area_creation_authorization(
    super_admin_user: User, officer_a_user: User, civilian_user: User, area_a: Area
) -> None:
    """Verify authorization for POST /api/v1/areas."""
    with patch.object(AreaService, "create_area", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = area_a

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            payload = {"name": "North District", "code": "AREA-NORTH"}

            # 1. Super Admin -> 201 Created
            app.dependency_overrides[get_current_user] = lambda: super_admin_user
            res1 = await ac.post("/api/v1/areas", json=payload)
            assert res1.status_code == 201
            assert res1.json()["code"] == "AREA-NORTH"

            # 2. Area Officer -> 403 Forbidden
            app.dependency_overrides[get_current_user] = lambda: officer_a_user
            res2 = await ac.post("/api/v1/areas", json=payload)
            assert res2.status_code == 403

            # 3. Civilian -> 403 Forbidden
            app.dependency_overrides[get_current_user] = lambda: civilian_user
            res3 = await ac.post("/api/v1/areas", json=payload)
            assert res3.status_code == 403
    app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_area_listing_authorization(
    super_admin_user: User, officer_a_user: User, civilian_user: User, area_a: Area
) -> None:
    """Verify authorization for GET /api/v1/areas."""
    paginated_areas = PaginatedResponse.create(
        items=[AreaResponse.model_validate(area_a)],
        total=1,
        page=1,
        page_size=20,
    )
    with patch.object(AreaService, "list_areas", new_callable=AsyncMock) as mock_list:
        mock_list.return_value = paginated_areas

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            # 1. Super Admin -> 200 OK
            app.dependency_overrides[get_current_user] = lambda: super_admin_user
            res1 = await ac.get("/api/v1/areas")
            assert res1.status_code == 200
            assert len(res1.json()["items"]) == 1

            # 2. Area Officer -> 200 OK
            app.dependency_overrides[get_current_user] = lambda: officer_a_user
            res2 = await ac.get("/api/v1/areas")
            assert res2.status_code == 200

            # 3. Civilian -> 403 Forbidden
            app.dependency_overrides[get_current_user] = lambda: civilian_user
            res3 = await ac.get("/api/v1/areas")
            assert res3.status_code == 403
    app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_area_update_and_deactivation_authorization(
    super_admin_user: User, officer_a_user: User, civilian_user: User, area_a: Area
) -> None:
    """Verify authorization for PATCH and DELETE /api/v1/areas/{id}."""
    with patch.object(AreaService, "update_area", new_callable=AsyncMock) as mock_upd, \
         patch.object(AreaService, "deactivate_area", new_callable=AsyncMock) as mock_deact:
        mock_upd.return_value = area_a
        mock_deact.return_value = area_a

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            area_id = str(area_a.id)

            # 1. Super Admin update -> 200 OK
            app.dependency_overrides[get_current_user] = lambda: super_admin_user
            res1 = await ac.patch(f"/api/v1/areas/{area_id}", json={"name": "New Name"})
            assert res1.status_code == 200

            # 2. Super Admin delete -> 200 OK
            res2 = await ac.delete(f"/api/v1/areas/{area_id}")
            assert res2.status_code == 200

            # 3. Officer update -> 403 Forbidden
            app.dependency_overrides[get_current_user] = lambda: officer_a_user
            res3 = await ac.patch(f"/api/v1/areas/{area_id}", json={"name": "New Name"})
            assert res3.status_code == 403

            # 4. Civilian delete -> 403 Forbidden
            app.dependency_overrides[get_current_user] = lambda: civilian_user
            res4 = await ac.delete(f"/api/v1/areas/{area_id}")
            assert res4.status_code == 403
    app.dependency_overrides.clear()
