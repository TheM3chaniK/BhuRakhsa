import io
from unittest.mock import AsyncMock, patch
import pytest
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_current_user
from app.main import app
from app.models.user import User
from app.services.reference_import_service import ReferenceImportService


@pytest.mark.anyio
async def test_reference_import_flow(
    super_admin_user: User, civilian_user: User
) -> None:
    """Verify reference dataset upload by Super Admin and rejection for Civilians."""
    csv_content = (
        "source_id,source_record_id,survey_number,plot_number,parcel_number,owner_names,property_area,area_unit,district,village\n"
        "state_registry,REC-001,123/45,7,P-001,Ramesh Kumar,2.50,acres,Pune,Shanti Nagar\n"
        "state_registry,REC-002,999/12,8,P-002,Suresh Kumar,1.20,acres,Pune,Shanti Nagar\n"
    )

    mock_summary = {
        "total_records": 2,
        "inserted": 2,
        "updated": 0,
        "failed": 0,
    }

    with patch.object(
        ReferenceImportService, "import_reference_dataset", new_callable=AsyncMock
    ) as mock_import:
        mock_import.return_value = mock_summary

        # 1. Super Admin uploads CSV dataset -> 200 OK
        app.dependency_overrides[get_current_user] = lambda: super_admin_user
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            files = {
                "file": ("reference.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")
            }
            res = await ac.post(
                "/api/v1/admin/reference-properties/import",
                files=files,
                data={"dataset_version": "2026-08-27"},
            )
            assert res.status_code == 200
            data = res.json()
            assert data["total_records"] == 2
            assert data["inserted"] == 2

        # 2. Civilian attempts to upload dataset -> 403 Forbidden
        app.dependency_overrides[get_current_user] = lambda: civilian_user
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            files = {
                "file": ("reference.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")
            }
            res_civ = await ac.post(
                "/api/v1/admin/reference-properties/import",
                files=files,
            )
            assert res_civ.status_code == 403

    app.dependency_overrides.clear()
