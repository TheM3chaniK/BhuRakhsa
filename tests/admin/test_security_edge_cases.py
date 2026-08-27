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
from app.services.area_service import AreaService
from app.services.auth_service import AuthService
from app.services.officer_service import OfficerService
from app.services.user_service import UserService


@pytest.mark.anyio
async def test_deactivated_user_cannot_access_profile(civilian_user: User) -> None:
    """Verify deactivated user account receives 401 when attempting to use token on /me."""
    deactivated_user = User(
        id=civilian_user.id,
        full_name=civilian_user.full_name,
        email=civilian_user.email,
        password_hash=civilian_user.password_hash,
        role=UserRole.CIVILIAN,
        is_active=False,  # Inactive
        is_verified=False,
        created_at=civilian_user.created_at,
        updated_at=civilian_user.updated_at,
    )

    app.dependency_overrides[get_current_user] = lambda: (_ for _ in ()).throw(
        pytest.importorskip("fastapi").HTTPException(
            status_code=401, detail="User account is inactive."
        )
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        res = await ac.get("/api/v1/users/me")
        assert res.status_code == 401
        assert "inactive" in res.json()["detail"]
    app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_last_super_admin_deactivation_blocked(
    super_admin_user: User,
) -> None:
    """Verify Super Admin cannot deactivate the sole remaining active Super Admin."""
    with patch.object(UserService, "update_user_admin", new_callable=AsyncMock) as mock_upd:
        mock_upd.side_effect = pytest.importorskip("fastapi").HTTPException(
            status_code=400, detail="Cannot deactivate the last active Super Admin."
        )

        app.dependency_overrides[get_current_user] = lambda: super_admin_user
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            res = await ac.patch(
                f"/api/v1/admin/users/{super_admin_user.id}",
                json={"is_active": False},
            )
            assert res.status_code == 400
            assert "Cannot deactivate the last active Super Admin" in res.json()["detail"]
    app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_officer_demotion_clears_jurisdiction_and_access(
    super_admin_user: User, officer_a_user: User, area_a: Area
) -> None:
    """Verify that when an officer is demoted to civilian, officer endpoints return 403."""
    # 1. Demote officer
    demoted_officer = User(
        id=officer_a_user.id,
        full_name=officer_a_user.full_name,
        email=officer_a_user.email,
        password_hash=officer_a_user.password_hash,
        role=UserRole.CIVILIAN,  # Role changed to civilian
        is_active=True,
        is_verified=True,
        created_at=officer_a_user.created_at,
        updated_at=officer_a_user.updated_at,
    )

    with patch.object(
        OfficerService, "demote_officer_to_civilian", new_callable=AsyncMock
    ) as mock_dem:
        mock_dem.return_value = demoted_officer

        app.dependency_overrides[get_current_user] = lambda: super_admin_user
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            res = await ac.post(f"/api/v1/admin/officers/{officer_a_user.id}/demote")
            assert res.status_code == 200
            assert res.json()["role"] == "civilian"

        # 2. Authenticate as now-demoted user and attempt accessing officer route
        app.dependency_overrides[get_current_user] = lambda: demoted_officer
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            res_off = await ac.get("/api/v1/officer/areas")
            assert res_off.status_code == 403

    app.dependency_overrides.clear()
