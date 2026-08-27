from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_current_user
from app.main import app
from app.models.area import Area
from app.models.area_officer_assignment import AreaOfficerAssignment
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.area import AreaResponse
from app.schemas.officer import OfficerDetailResponse
from app.schemas.pagination import PaginatedResponse
from app.services.officer_service import OfficerService


@pytest.mark.anyio
async def test_admin_officers_list_and_detail(
    super_admin_user: User, officer_a_user: User, area_a: Area
) -> None:
    """Verify paginated officer list and detail retrieval for Super Admin."""
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
        areas=[AreaResponse.model_validate(area_a)],
    )
    paginated = PaginatedResponse.create(
        items=[detail], total=1, page=1, page_size=20
    )

    with patch.object(OfficerService, "list_officers", new_callable=AsyncMock) as mock_list, \
         patch.object(OfficerService, "get_officer", new_callable=AsyncMock) as mock_get:
        mock_list.return_value = paginated
        mock_get.return_value = detail

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            app.dependency_overrides[get_current_user] = lambda: super_admin_user
            officer_id = str(officer_a_user.id)

            # List officers -> 200
            res1 = await ac.get("/api/v1/admin/officers")
            assert res1.status_code == 200
            assert len(res1.json()["items"]) == 1
            assert len(res1.json()["items"][0]["areas"]) == 1

            # Get officer detail -> 200
            res2 = await ac.get(f"/api/v1/admin/officers/{officer_id}")
            assert res2.status_code == 200
            assert res2.json()["id"] == officer_id
            assert len(res2.json()["areas"]) == 1
    app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_admin_demote_officer(
    super_admin_user: User, officer_a_user: User
) -> None:
    """Verify POST /api/v1/admin/officers/{officer_id}/demote."""
    demoted_user = User(
        id=officer_a_user.id,
        full_name=officer_a_user.full_name,
        email=officer_a_user.email,
        phone=officer_a_user.phone,
        password_hash=officer_a_user.password_hash,
        role=UserRole.CIVILIAN,
        is_active=True,
        is_verified=True,
        created_at=officer_a_user.created_at,
        updated_at=officer_a_user.updated_at,
    )

    with patch.object(
        OfficerService, "demote_officer_to_civilian", new_callable=AsyncMock
    ) as mock_dem:
        mock_dem.return_value = demoted_user

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            app.dependency_overrides[get_current_user] = lambda: super_admin_user
            officer_id = str(officer_a_user.id)

            res = await ac.post(f"/api/v1/admin/officers/{officer_id}/demote")
            assert res.status_code == 200
            assert res.json()["role"] == "civilian"
    app.dependency_overrides.clear()
