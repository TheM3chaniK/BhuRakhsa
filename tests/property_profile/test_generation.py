from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
import uuid

from fastapi import HTTPException
import pytest
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_current_user
from app.main import app
from app.models.enums import OwnershipType, ProfileStatus
from app.models.property_owner import PropertyOwner
from app.models.property_profile import PropertyProfile
from app.models.user import User
from app.schemas.property_profile import (
    PropertyFieldSourceResponse,
    PropertyOwnerResponse,
    PropertyProfileResponse,
)
from app.services.property_profile_service import PropertyProfileService


@pytest.mark.anyio
async def test_property_profile_generation_and_retrieval(civilian_user: User) -> None:
    """Verify property profile generate, get, and refresh API endpoints."""
    case_id = uuid.uuid4()
    profile_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    mock_profile = PropertyProfile(
        id=profile_id,
        case_id=case_id,
        status=ProfileStatus.EXTRACTED,
        property_identifier="SURVEY-123/45-SHANTI NAGAR",
        survey_number="123/45",
        plot_number="42",
        parcel_number="P-99",
        registration_number="REG-2025-001",
        deed_number="DEED-100",
        property_address="Plot 42, Shanti Nagar, Pune",
        district="Pune",
        village="Shanti Nagar",
        property_area=2.50,
        area_unit="acres",
        created_at=now,
        updated_at=now,
    )
    mock_profile.owners = [
        PropertyOwner(
            id=uuid.uuid4(),
            property_profile_id=profile_id,
            name="Ramesh Kumar",
            normalized_name="ramesh kumar",
            ownership_type=OwnershipType.INDIVIDUAL,
            created_at=now,
            updated_at=now,
        )
    ]
    mock_profile.field_sources = []
    mock_profile.conflicts = []

    with patch.object(
        PropertyProfileService, "generate_profile", new_callable=AsyncMock
    ) as mock_gen, patch.object(
        PropertyProfileService, "get_profile", new_callable=AsyncMock
    ) as mock_get:

        mock_gen.return_value = mock_profile
        mock_get.return_value = mock_profile

        app.dependency_overrides[get_current_user] = lambda: civilian_user
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            # 1. Generate canonical profile -> 201 Created
            res_gen = await ac.post(
                f"/api/v1/cases/{case_id}/property-profile/generate"
            )
            assert res_gen.status_code == 201
            data_gen = res_gen.json()
            assert data_gen["id"] == str(profile_id)
            assert data_gen["case_id"] == str(case_id)
            assert data_gen["survey_number"] == "123/45"
            assert data_gen["property_area"] == 2.50
            assert len(data_gen["owners"]) == 1
            assert data_gen["owners"][0]["name"] == "Ramesh Kumar"

            # 2. Get canonical profile -> 200 OK
            res_get = await ac.get(f"/api/v1/cases/{case_id}/property-profile")
            assert res_get.status_code == 200
            data_get_res = res_get.json()
            assert data_get_res["status"] == "extracted"
            assert data_get_res["survey_number"] == "123/45"

            # 3. Refresh profile -> 200 OK
            res_ref = await ac.post(
                f"/api/v1/cases/{case_id}/property-profile/refresh"
            )
            assert res_ref.status_code == 200

            # 4. Generate profile without completed extraction -> 409 Conflict
            mock_gen.side_effect = HTTPException(
                status_code=409,
                detail="Extraction has not completed for any case documents.",
            )
            res_conflict = await ac.post(
                f"/api/v1/cases/{case_id}/property-profile/generate"
            )
            assert res_conflict.status_code == 409

    app.dependency_overrides.clear()
