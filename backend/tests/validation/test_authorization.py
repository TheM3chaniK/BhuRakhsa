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
async def test_validation_authorization_isolation(
    civilian_user: User, civilian_b_user: User, officer_b_user: User
) -> None:
    """Verify validation result access control: civilian views own results, unauthorized users receive 403."""
    run_id = uuid.uuid4()
    profile_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    mock_run = ValidationRun(
        id=run_id,
        property_profile_id=profile_id,
        validation_type=ValidationType.DATABASE,
        status=ValidationStatus.PASSED,
        created_at=now,
        updated_at=now,
    )
    mock_run.results = [
        ValidationResult(
            id=uuid.uuid4(),
            validation_run_id=run_id,
            field_name="survey_number",
            document_value="123/45",
            reference_value="123/45",
            match_status=MatchStatus.MATCH,
            match_score=1.0,
            source_id="state_registry",
            source_record_id="REC-001",
            created_at=now,
        )
    ]
    mock_run.candidates = []

    with patch.object(
        PropertyProfileService, "get_validation_run", new_callable=AsyncMock
    ) as mock_get_run:
        mock_get_run.return_value = mock_run

        # 1. Civilian A views own validation results -> 200 OK (reference_value & source masked)
        app.dependency_overrides[get_current_user] = lambda: civilian_user
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            res = await ac.get(f"/api/v1/validation-runs/{run_id}/results")
            assert res.status_code == 200
            data = res.json()
            assert len(data) == 1
            assert data[0]["field_name"] == "survey_number"
            assert data[0]["document_value"] == "123/45"
            assert data[0]["reference_value"] is None  # Sanitized for civilians

        # 2. Civilian B unauthorized -> 403 Forbidden
        mock_get_run.side_effect = HTTPException(
            status_code=403,
            detail="You do not have permission to access this case.",
        )
        app.dependency_overrides[get_current_user] = lambda: civilian_b_user
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            res_b = await ac.get(f"/api/v1/validation-runs/{run_id}/results")
            assert res_b.status_code == 403

        # 3. Officer outside area -> 403 Forbidden
        app.dependency_overrides[get_current_user] = lambda: officer_b_user
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            res_off = await ac.get(f"/api/v1/validation-runs/{run_id}/results")
            assert res_off.status_code == 403

    app.dependency_overrides.clear()
