from unittest.mock import AsyncMock, patch
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_current_user
from app.main import app
from app.models.area import Area
from app.models.user import User
from app.services.area_service import AreaService


@pytest.mark.anyio
async def test_critical_area_isolation(
    super_admin_user: User,
    officer_a_user: User,
    officer_b_user: User,
    civilian_user: User,
    area_a: Area,
    area_b: Area,
) -> None:
    """CRITICAL SECURITY TEST: Verify strict geographical boundary isolation between Area Officers.

    - Officer A (assigned to Area A) can access Area A but is FORBIDDEN from Area B.
    - Officer B (assigned to Area B) can access Area B but is FORBIDDEN from Area A.
    - Super Admin can access BOTH Area A and Area B.
    - Civilian is FORBIDDEN from both areas.
    """
    area_a_id = area_a.id
    area_b_id = area_b.id

    async def mock_check_access(db, user: User, area_id: uuid.UUID) -> bool:
        if user.role == "super_admin":
            return True
        if user.id == officer_a_user.id and area_id == area_a_id:
            return True
        if user.id == officer_b_user.id and area_id == area_b_id:
            return True
        return False

    async def mock_get_area(db, area_id: uuid.UUID) -> Area | None:
        if area_id == area_a_id:
            return area_a
        if area_id == area_b_id:
            return area_b
        return None

    with patch.object(
        AreaService, "check_officer_area_access", side_effect=mock_check_access
    ), patch.object(AreaService, "get_area", side_effect=mock_get_area):

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            # -----------------------------------------------------------------
            # 1. Officer A Tests
            # -----------------------------------------------------------------
            app.dependency_overrides[get_current_user] = lambda: officer_a_user

            # Officer A -> Area A (Assigned) -> 200 OK
            res_a_a = await ac.get(f"/api/v1/areas/{area_a_id}")
            assert res_a_a.status_code == 200
            assert res_a_a.json()["id"] == str(area_a_id)

            # Officer A -> Area B (Unassigned) -> 403 FORBIDDEN
            res_a_b = await ac.get(f"/api/v1/areas/{area_b_id}")
            assert res_a_b.status_code == 403

            # -----------------------------------------------------------------
            # 2. Officer B Tests
            # -----------------------------------------------------------------
            app.dependency_overrides[get_current_user] = lambda: officer_b_user

            # Officer B -> Area B (Assigned) -> 200 OK
            res_b_b = await ac.get(f"/api/v1/areas/{area_b_id}")
            assert res_b_b.status_code == 200
            assert res_b_b.json()["id"] == str(area_b_id)

            # Officer B -> Area A (Unassigned) -> 403 FORBIDDEN
            res_b_a = await ac.get(f"/api/v1/areas/{area_a_id}")
            assert res_b_a.status_code == 403

            # -----------------------------------------------------------------
            # 3. Super Admin Tests (Global Access)
            # -----------------------------------------------------------------
            app.dependency_overrides[get_current_user] = lambda: super_admin_user

            # Super Admin -> Area A -> 200 OK
            res_admin_a = await ac.get(f"/api/v1/areas/{area_a_id}")
            assert res_admin_a.status_code == 200

            # Super Admin -> Area B -> 200 OK
            res_admin_b = await ac.get(f"/api/v1/areas/{area_b_id}")
            assert res_admin_b.status_code == 200

            # -----------------------------------------------------------------
            # 4. Civilian Tests (Restricted)
            # -----------------------------------------------------------------
            app.dependency_overrides[get_current_user] = lambda: civilian_user

            # Civilian -> Area A -> 403 FORBIDDEN
            res_civ_a = await ac.get(f"/api/v1/areas/{area_a_id}")
            assert res_civ_a.status_code == 403

            # Civilian -> Area B -> 403 FORBIDDEN
            res_civ_b = await ac.get(f"/api/v1/areas/{area_b_id}")
            assert res_civ_b.status_code == 403

    app.dependency_overrides.clear()
