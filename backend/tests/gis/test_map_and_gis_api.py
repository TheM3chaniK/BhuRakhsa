from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
import uuid

from fastapi import HTTPException
import pytest
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_current_user
from app.main import app
from app.models.enums import MatchStatus, ValidationStatus, ValidationType
from app.models.user import User
from app.models.validation import ValidationRun
from app.models.validation_result import ValidationResult
from app.services.property_profile_service import PropertyProfileService


@pytest.mark.anyio
async def test_map_and_gis_validation_endpoints(
    civilian_user: User, civilian_b_user: User, officer_a_user: User
) -> None:
    """Verify Map data retrieval and structured GIS checks endpoints with RBAC isolation."""
    case_id = uuid.uuid4()
    run_id = uuid.uuid4()
    profile_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    mock_map_data = {
        "case_id": case_id,
        "property_identifier": "SURVEY-123/45-PUNE",
        "property_point": {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [73.0005, 20.0005]},
            "properties": {"source": "document", "latitude": 20.0005, "longitude": 73.0005},
        },
        "reference_parcel": {
            "type": "Feature",
            "geometry": {
                "type": "MultiPolygon",
                "coordinates": [[[[73.0, 20.0], [73.001, 20.0], [73.001, 20.001], [73.0, 20.001], [73.0, 20.0]]]],
            },
            "properties": {"source_id": "state_gis", "source_record_id": "P-001", "area": 10117.14, "area_unit": "sq_meters"},
        },
        "gis_validation_status": "passed",
    }

    mock_gis_run = ValidationRun(
        id=run_id,
        property_profile_id=profile_id,
        validation_type=ValidationType.GIS,
        status=ValidationStatus.PASSED,
        created_at=now,
        updated_at=now,
    )
    mock_gis_run.results = [
        ValidationResult(
            id=uuid.uuid4(),
            validation_run_id=run_id,
            field_name="parcel_geometry",
            match_status=MatchStatus.MATCH,
            document_value=None,
            reference_value="VALID",
            match_score=1.0,
            created_at=now,
        ),
        ValidationResult(
            id=uuid.uuid4(),
            validation_run_id=run_id,
            field_name="point_inside_parcel",
            match_status=MatchStatus.MATCH,
            document_value="POINT(20.000500, 73.000500)",
            reference_value="Inside Parcel P-001",
            match_score=1.0,
            geometry_distance_meters=0.0,
            coordinate_latitude=20.0005,
            coordinate_longitude=73.0005,
            created_at=now,
        ),
    ]
    mock_gis_run.candidates = []

    with patch.object(
        PropertyProfileService, "get_case_map_data", new_callable=AsyncMock
    ) as mock_get_map, patch.object(
        PropertyProfileService, "get_validation_run", new_callable=AsyncMock
    ) as mock_get_run:

        mock_get_map.return_value = mock_map_data
        mock_get_run.return_value = mock_gis_run

        # 1. Civilian views own case map data -> 200 OK
        app.dependency_overrides[get_current_user] = lambda: civilian_user
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            res_map = await ac.get(f"/api/v1/cases/{case_id}/property-profile/map")
            assert res_map.status_code == 200
            data_map = res_map.json()
            assert data_map["property_point"]["geometry"]["type"] == "Point"
            assert data_map["reference_parcel"]["geometry"]["type"] == "MultiPolygon"
            assert data_map["gis_validation_status"] == "passed"

            # 2. Get GIS validation run checks -> 200 OK
            res_gis = await ac.get(f"/api/v1/validation-runs/{run_id}/gis")
            assert res_gis.status_code == 200
            data_gis = res_gis.json()
            assert data_gis["status"] == "passed"
            assert len(data_gis["checks"]) == 2

        # 3. Civilian B unauthorized -> 403 Forbidden
        mock_get_map.side_effect = HTTPException(
            status_code=403,
            detail="You do not have permission to access this case.",
        )
        app.dependency_overrides[get_current_user] = lambda: civilian_b_user
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            res_b = await ac.get(f"/api/v1/cases/{case_id}/property-profile/map")
            assert res_b.status_code == 403

    app.dependency_overrides.clear()
