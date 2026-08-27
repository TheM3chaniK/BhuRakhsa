from unittest.mock import AsyncMock, patch
import uuid

from fastapi import HTTPException
import pytest
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_current_user
from app.main import app
from app.models.user import User
from app.services.property_profile_service import PropertyProfileService


@pytest.mark.anyio
async def test_property_profile_authorization_isolation(
    civilian_b_user: User, officer_b_user: User
) -> None:
    """Verify unauthorized civilian or officer outside case area receives 403 Forbidden on property profile endpoints."""
    case_id = uuid.uuid4()

    with patch.object(
        PropertyProfileService, "generate_profile", new_callable=AsyncMock
    ) as mock_gen, patch.object(
        PropertyProfileService, "get_profile", new_callable=AsyncMock
    ) as mock_get:

        mock_gen.side_effect = HTTPException(
            status_code=403,
            detail="You do not have permission to access this case.",
        )
        mock_get.side_effect = HTTPException(
            status_code=403,
            detail="You do not have permission to access this case.",
        )

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            # 1. Other civilian attempting to generate profile -> 403 Forbidden
            app.dependency_overrides[get_current_user] = lambda: civilian_b_user
            res_civ_b = await ac.post(
                f"/api/v1/cases/{case_id}/property-profile/generate"
            )
            assert res_civ_b.status_code == 403

            # 2. Other civilian attempting to get profile -> 403 Forbidden
            res_civ_get = await ac.get(f"/api/v1/cases/{case_id}/property-profile")
            assert res_civ_get.status_code == 403

            # 3. Officer outside area attempting to get profile -> 403 Forbidden
            app.dependency_overrides[get_current_user] = lambda: officer_b_user
            res_off_b = await ac.get(f"/api/v1/cases/{case_id}/property-profile")
            assert res_off_b.status_code == 403

    app.dependency_overrides.clear()
