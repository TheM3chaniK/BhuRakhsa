from unittest.mock import AsyncMock, patch
import uuid

from fastapi import HTTPException, status
import pytest
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_current_user
from app.main import app
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.pagination import PaginatedResponse
from app.schemas.user import UserResponse
from app.services.user_service import UserService


@pytest.mark.anyio
async def test_admin_list_users(
    super_admin_user: User, civilian_user: User
) -> None:
    """Verify GET /api/v1/admin/users permissions and pagination."""
    paginated_users = PaginatedResponse.create(
        items=[UserResponse.model_validate(civilian_user)],
        total=1,
        page=1,
        page_size=20,
    )

    with patch.object(UserService, "list_users", new_callable=AsyncMock) as mock_list:
        mock_list.return_value = paginated_users

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            # 1. Super Admin -> 200 OK
            app.dependency_overrides[get_current_user] = lambda: super_admin_user
            res1 = await ac.get("/api/v1/admin/users")
            assert res1.status_code == 200
            assert len(res1.json()["items"]) == 1
            assert res1.json()["total"] == 1

            # 2. Civilian -> 403 Forbidden
            app.dependency_overrides[get_current_user] = lambda: civilian_user
            res2 = await ac.get("/api/v1/admin/users")
            assert res2.status_code == 403
    app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_admin_get_and_update_user(
    super_admin_user: User, civilian_user: User
) -> None:
    """Verify Super Admin GET & PATCH /api/v1/admin/users/{user_id}."""
    with patch.object(UserService, "get_user_by_id", new_callable=AsyncMock) as mock_get, \
         patch.object(UserService, "update_user_admin", new_callable=AsyncMock) as mock_upd:
        mock_get.return_value = civilian_user
        mock_upd.return_value = civilian_user

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            app.dependency_overrides[get_current_user] = lambda: super_admin_user
            user_id = str(civilian_user.id)

            # Get user -> 200
            res1 = await ac.get(f"/api/v1/admin/users/{user_id}")
            assert res1.status_code == 200
            assert res1.json()["id"] == user_id

            # Update user status -> 200
            res2 = await ac.patch(
                f"/api/v1/admin/users/{user_id}",
                json={"is_active": False},
            )
            assert res2.status_code == 200
    app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_admin_promote_civilian_to_officer(
    super_admin_user: User, civilian_user: User
) -> None:
    """Verify Super Admin POST /api/v1/admin/users/{user_id}/promote-to-officer."""
    promoted_officer = User(
        id=civilian_user.id,
        full_name=civilian_user.full_name,
        email=civilian_user.email,
        phone=civilian_user.phone,
        password_hash=civilian_user.password_hash,
        role=UserRole.AREA_OFFICER,
        is_active=True,
        is_verified=True,
        created_at=civilian_user.created_at,
        updated_at=civilian_user.updated_at,
    )

    with patch.object(
        UserService, "promote_civilian_to_officer", new_callable=AsyncMock
    ) as mock_prom:
        mock_prom.return_value = promoted_officer

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            app.dependency_overrides[get_current_user] = lambda: super_admin_user
            user_id = str(civilian_user.id)

            res = await ac.post(f"/api/v1/admin/users/{user_id}/promote-to-officer")
            assert res.status_code == 200
            assert res.json()["role"] == "area_officer"
    app.dependency_overrides.clear()
