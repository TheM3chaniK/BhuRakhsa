from unittest.mock import AsyncMock, patch
import uuid
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
import pytest

from app.api.dependencies import get_current_user
from app.main import app
from app.models.user import User
from app.services.area_service import AreaService


@pytest.mark.anyio
async def test_area_deactivation_with_active_cases_blocked(super_admin_user: User) -> None:
    """Verify that deactivating an area with active cases returns 409 Conflict."""
    area_id = uuid.uuid4()

    with patch.object(
        AreaService, "update_area", new_callable=AsyncMock
    ) as mock_update:
        mock_update.side_effect = HTTPException(
            status_code=409,
            detail="Cannot deactivate area 'North District'. There are 3 active in-flight cases that must be finalized first.",
        )

        app.dependency_overrides[get_current_user] = lambda: super_admin_user
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            res = await ac.patch(
                f"/api/v1/admin/areas/{area_id}",
                json={"is_active": False},
            )
            assert res.status_code == 409
            assert "active in-flight cases" in res.json()["detail"]

        app.dependency_overrides.clear()
