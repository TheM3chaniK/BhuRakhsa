from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_current_user
from app.main import app
from app.models.area import Area
from app.models.area_officer_assignment import AreaOfficerAssignment
from app.models.user import User
from app.schemas.officer import OfficerDetailResponse
from app.schemas.pagination import PaginatedResponse
from app.services.officer_service import OfficerService


@pytest.mark.anyio
async def test_admin_officer_management_authorization(
    super_admin_user: User, officer_a_user: User, civilian_user: User, area_a: Area
) -> None:
    """Verify Super Admin permissions on /api/v1/admin/officers endpoints."""
    now = datetime.now(timezone.utc)
    mock_assignment = AreaOfficerAssignment(
        id=uuid.uuid4(),
        officer_id=officer_a_user.id,
        area_id=area_a.id,
        created_at=now,
    )
    detail = OfficerDetailResponse(
        id=officer_a_user.id,
        full_name=officer_a_user.full_name,
        email=officer_a_user.email,
        phone=officer_a_user.phone,
        role="area_officer",
        is_active=True,
        is_verified=True,
        created_at=officer_a_user.created_at,
        last_login_at=officer_a_user.last_login_at,
        areas=[],
    )
    paginated = PaginatedResponse.create(
        items=[detail], total=1, page=1, page_size=20
    )

    with patch.object(OfficerService, "create_officer", new_callable=AsyncMock) as mock_create, \
         patch.object(OfficerService, "list_officers", new_callable=AsyncMock) as mock_list, \
         patch.object(OfficerService, "get_officer", new_callable=AsyncMock) as mock_get, \
         patch.object(OfficerService, "update_officer", new_callable=AsyncMock) as mock_upd, \
         patch.object(OfficerService, "assign_area", new_callable=AsyncMock) as mock_assign, \
         patch.object(OfficerService, "remove_area", new_callable=AsyncMock) as mock_remove, \
         patch.object(OfficerService, "get_officer_areas", new_callable=AsyncMock) as mock_officer_areas:

        mock_create.return_value = officer_a_user
        mock_list.return_value = paginated
        mock_get.return_value = detail
        mock_upd.return_value = officer_a_user
        mock_assign.return_value = mock_assignment
        mock_remove.return_value = None
        mock_officer_areas.return_value = [area_a]

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            officer_id = str(officer_a_user.id)
            area_id = str(area_a.id)

            # -----------------------------------------------------------------
            # 1. Super Admin Tests (Allowed)
            # -----------------------------------------------------------------
            app.dependency_overrides[get_current_user] = lambda: super_admin_user

            # List officers -> 200
            res_list = await ac.get("/api/v1/admin/officers")
            assert res_list.status_code == 200

            # Get officer -> 200
            res_get = await ac.get(f"/api/v1/admin/officers/{officer_id}")
            assert res_get.status_code == 200

            # Create officer -> 201
            res_create = await ac.post(
                "/api/v1/admin/officers",
                json={
                    "full_name": "New Officer",
                    "email": "new.officer@example.com",
                    "password": "Password123!",
                },
            )
            assert res_create.status_code == 201
            assert res_create.json()["role"] == "area_officer"

            # Update officer -> 200
            res_upd = await ac.patch(
                f"/api/v1/admin/officers/{officer_id}",
                json={"is_active": False},
            )
            assert res_upd.status_code == 200

            # Assign officer to area -> 201
            res_assign = await ac.post(
                f"/api/v1/admin/officers/{officer_id}/areas/{area_id}"
            )
            assert res_assign.status_code == 201
            assert res_assign.json()["officer_id"] == officer_id

            # Get officer's areas -> 200
            res_areas = await ac.get(f"/api/v1/admin/officers/{officer_id}/areas")
            assert res_areas.status_code == 200
            assert len(res_areas.json()) == 1

            # Remove assignment -> 200
            res_rem = await ac.delete(
                f"/api/v1/admin/officers/{officer_id}/areas/{area_id}"
            )
            assert res_rem.status_code == 200

            # -----------------------------------------------------------------
            # 2. Officer & Civilian Tests (Forbidden)
            # -----------------------------------------------------------------
            app.dependency_overrides[get_current_user] = lambda: officer_a_user
            res_off_list = await ac.get("/api/v1/admin/officers")
            assert res_off_list.status_code == 403

            app.dependency_overrides[get_current_user] = lambda: civilian_user
            res_civ_create = await ac.post(
                "/api/v1/admin/officers",
                json={"full_name": "Test", "email": "t@t.com", "password": "Password123!"},
            )
            assert res_civ_create.status_code == 403

    app.dependency_overrides.clear()
