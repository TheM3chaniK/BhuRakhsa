from fastapi import APIRouter, Depends, status
import pytest
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_current_user, require_role
from app.main import app
from app.models.enums import UserRole
from app.models.user import User

rbac_test_router = APIRouter(prefix="/test-rbac")


@rbac_test_router.get("/admin-only")
async def admin_only_route(
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN)),
) -> dict:
    return {"status": "success", "user": current_user.email}


@rbac_test_router.get("/staff-only")
async def staff_only_route(
    current_user: User = Depends(
        require_role(UserRole.SUPER_ADMIN, UserRole.AREA_OFFICER)
    ),
) -> dict:
    return {"status": "success", "user": current_user.email}


app.include_router(rbac_test_router)


@pytest.mark.anyio
async def test_admin_only_rbac(
    super_admin_user: User, officer_a_user: User, civilian_user: User
) -> None:
    """Verify require_role(SUPER_ADMIN) enforcement across roles."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        # 1. Super Admin -> 200 OK
        app.dependency_overrides[get_current_user] = lambda: super_admin_user
        res1 = await ac.get("/test-rbac/admin-only")
        assert res1.status_code == 200
        assert res1.json()["status"] == "success"

        # 2. Area Officer -> 403 Forbidden
        app.dependency_overrides[get_current_user] = lambda: officer_a_user
        res2 = await ac.get("/test-rbac/admin-only")
        assert res2.status_code == 403

        # 3. Civilian -> 403 Forbidden
        app.dependency_overrides[get_current_user] = lambda: civilian_user
        res3 = await ac.get("/test-rbac/admin-only")
        assert res3.status_code == 403
    app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_staff_rbac(
    super_admin_user: User, officer_a_user: User, civilian_user: User
) -> None:
    """Verify require_role(SUPER_ADMIN, AREA_OFFICER) enforcement."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        # 1. Super Admin -> 200 OK
        app.dependency_overrides[get_current_user] = lambda: super_admin_user
        res1 = await ac.get("/test-rbac/staff-only")
        assert res1.status_code == 200

        # 2. Area Officer -> 200 OK
        app.dependency_overrides[get_current_user] = lambda: officer_a_user
        res2 = await ac.get("/test-rbac/staff-only")
        assert res2.status_code == 200

        # 3. Civilian -> 403 Forbidden
        app.dependency_overrides[get_current_user] = lambda: civilian_user
        res3 = await ac.get("/test-rbac/staff-only")
        assert res3.status_code == 403
    app.dependency_overrides.clear()
