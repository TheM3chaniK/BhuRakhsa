from unittest.mock import AsyncMock, patch
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_current_user
from app.main import app
from app.models.enums import UserRole
from app.models.user import User
from app.services.user_service import UserService


@pytest.mark.anyio
async def test_get_my_profile(civilian_user: User) -> None:
    """Verify GET /api/v1/users/me returns authenticated user's profile."""
    app.dependency_overrides[get_current_user] = lambda: civilian_user
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        res = await ac.get("/api/v1/users/me")
        assert res.status_code == 200
        data = res.json()
        assert data["id"] == str(civilian_user.id)
        assert data["email"] == civilian_user.email
        assert data["role"] == "civilian"
        assert "password_hash" not in data
        assert "refresh_tokens" not in data
    app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_update_my_profile(civilian_user: User) -> None:
    """Verify PATCH /api/v1/users/me updates allowed profile fields only."""
    with patch.object(UserService, "update_profile", new_callable=AsyncMock) as mock_upd:
        updated_user = User(
            id=civilian_user.id,
            full_name="Updated Citizen",
            email=civilian_user.email,
            phone="+919876543210",
            password_hash=civilian_user.password_hash,
            role=UserRole.CIVILIAN,
            is_active=True,
            is_verified=False,
            created_at=civilian_user.created_at,
            updated_at=civilian_user.updated_at,
            last_login_at=civilian_user.last_login_at,
        )
        mock_upd.return_value = updated_user

        app.dependency_overrides[get_current_user] = lambda: civilian_user
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            res = await ac.patch(
                "/api/v1/users/me",
                json={
                    "full_name": "Updated Citizen",
                    "phone": "+919876543210",
                    "role": "super_admin",  # Client tries to change role
                },
            )
            assert res.status_code == 200
            data = res.json()
            assert data["full_name"] == "Updated Citizen"
            assert data["phone"] == "+919876543210"
            assert data["role"] == "civilian"  # Role remained civilian
    app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_change_password_success(civilian_user: User) -> None:
    """Verify POST /api/v1/users/me/change-password success flow."""
    with patch.object(UserService, "change_password", new_callable=AsyncMock) as mock_change:
        mock_change.return_value = None

        app.dependency_overrides[get_current_user] = lambda: civilian_user
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            res = await ac.post(
                "/api/v1/users/me/change-password",
                json={
                    "current_password": "OldPassword123!",
                    "new_password": "NewSecurePassword456!",
                },
            )
            assert res.status_code == 200
            assert "changed successfully" in res.json()["message"]
            mock_change.assert_called_once()
    app.dependency_overrides.clear()
