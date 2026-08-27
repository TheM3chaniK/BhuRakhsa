import io
import json
from unittest.mock import AsyncMock, patch
import pytest
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_current_user
from app.main import app
from app.models.user import User
from app.services.reference_spatial_import_service import ReferenceSpatialImportService


@pytest.mark.anyio
async def test_spatial_geojson_import_authorization(
    super_admin_user: User, civilian_user: User
) -> None:
    """Verify GeoJSON parcel & boundary upload by Super Admin and rejection for Civilians."""
    sample_geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [73.000, 20.000],
                            [73.001, 20.000],
                            [73.001, 20.001],
                            [73.000, 20.001],
                            [73.000, 20.000],
                        ]
                    ],
                },
                "properties": {
                    "source_id": "state_gis_portal",
                    "source_record_id": "PARCEL-001",
                    "area": 10117.14,
                    "area_unit": "sq_meters",
                },
            }
        ],
    }
    raw_bytes = json.dumps(sample_geojson).encode("utf-8")

    mock_summary = {
        "total_features": 1,
        "inserted": 1,
        "updated": 0,
        "failed": 0,
    }

    with patch.object(
        ReferenceSpatialImportService, "import_parcels_geojson", new_callable=AsyncMock
    ) as mock_import_parcels, patch.object(
        ReferenceSpatialImportService, "import_boundaries_geojson", new_callable=AsyncMock
    ) as mock_import_bounds:

        mock_import_parcels.return_value = mock_summary
        mock_import_bounds.return_value = mock_summary

        # 1. Super Admin uploads parcels GeoJSON -> 200 OK
        app.dependency_overrides[get_current_user] = lambda: super_admin_user
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            files = {
                "file": ("parcels.geojson", io.BytesIO(raw_bytes), "application/geo+json")
            }
            res_p = await ac.post(
                "/api/v1/admin/reference-parcels/import",
                files=files,
                data={"dataset_version": "2026-08-27"},
            )
            assert res_p.status_code == 200
            assert res_p.json()["inserted"] == 1

            # 2. Super Admin uploads boundaries GeoJSON -> 200 OK
            files_b = {
                "file": ("districts.geojson", io.BytesIO(raw_bytes), "application/geo+json")
            }
            res_b = await ac.post(
                "/api/v1/admin/reference-boundaries/import",
                files=files_b,
                data={"boundary_type": "district", "dataset_version": "2026-08-27"},
            )
            assert res_b.status_code == 200
            assert res_b.json()["inserted"] == 1

        # 3. Civilian attempts upload -> 403 Forbidden
        app.dependency_overrides[get_current_user] = lambda: civilian_user
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            files = {
                "file": ("parcels.geojson", io.BytesIO(raw_bytes), "application/geo+json")
            }
            res_civ = await ac.post(
                "/api/v1/admin/reference-parcels/import",
                files=files,
            )
            assert res_civ.status_code == 403

    app.dependency_overrides.clear()
