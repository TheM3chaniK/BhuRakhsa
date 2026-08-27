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
async def test_validation_run_foundation_lifecycle(
    officer_a_user: User, civilian_user: User
) -> None:
    """Verify validation run creation by Area Officer and rejection for Civilians."""
    case_id = uuid.uuid4()
    profile_id = uuid.uuid4()
    run_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    mock_run = ValidationRun(
        id=run_id,
        property_profile_id=profile_id,
        validation_type=ValidationType.DATABASE,
        status=ValidationStatus.PENDING,
        validator_version="1.0",
        created_at=now,
        updated_at=now,
    )
    mock_run.results = [
        ValidationResult(
            id=uuid.uuid4(),
            validation_run_id=run_id,
            field_name="survey_number",
            document_value="123/45",
            reference_value=None,
            match_status=MatchStatus.NOT_CHECKED,
            match_score=0.0,
            mismatch_reason=None,
            created_at=now,
        )
    ]
    mock_run.candidates = []

    with patch.object(
        PropertyProfileService, "create_validation_run", new_callable=AsyncMock
    ) as mock_create_run, patch.object(
        PropertyProfileService, "list_validation_runs", new_callable=AsyncMock
    ) as mock_list_runs, patch.object(
        PropertyProfileService, "get_validation_run", new_callable=AsyncMock
    ) as mock_get_run:

        mock_create_run.return_value = mock_run
        mock_list_runs.return_value = [mock_run]
        mock_get_run.return_value = mock_run

        # 1. Area Officer triggers validation run -> 201 Created (Pending)
        app.dependency_overrides[get_current_user] = lambda: officer_a_user
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            res_create = await ac.post(
                f"/api/v1/cases/{case_id}/property-profile/validation-runs",
                json={"validation_type": "database"},
            )
            assert res_create.status_code == 201
            data_create = res_create.json()
            assert data_create["id"] == str(run_id)
            assert data_create["validation_type"] == "database"
            assert data_create["status"] == "pending"

            # 2. List validation runs
            res_list = await ac.get(
                f"/api/v1/cases/{case_id}/property-profile/validation-runs"
            )
            assert res_list.status_code == 200
            data_list = res_list.json()
            assert len(data_list) == 1
            assert data_list[0]["status"] == "pending"

            # 3. Get validation run detail
            res_detail = await ac.get(f"/api/v1/validation-runs/{run_id}")
            assert res_detail.status_code == 200
            data_detail = res_detail.json()
            assert data_detail["id"] == str(run_id)
            assert len(data_detail["results"]) == 1
            assert data_detail["results"][0]["match_status"] == "not_checked"

            # 4. Invalid validation type -> 422 Unprocessable Entity
            res_invalid = await ac.post(
                f"/api/v1/cases/{case_id}/property-profile/validation-runs",
                json={"validation_type": "magic_type"},
            )
            assert res_invalid.status_code == 422

        # 5. Civilian triggers validation run -> 403 Forbidden
        mock_create_run.side_effect = HTTPException(
            status_code=403,
            detail="Civilians cannot trigger validation runs.",
        )
        app.dependency_overrides[get_current_user] = lambda: civilian_user
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            res_civ = await ac.post(
                f"/api/v1/cases/{case_id}/property-profile/validation-runs",
                json={"validation_type": "database"},
            )
            assert res_civ.status_code == 403

    app.dependency_overrides.clear()
