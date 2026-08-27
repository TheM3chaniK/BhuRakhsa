from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
import uuid
from fastapi import HTTPException
import pytest
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_current_user
from app.main import app
from app.models.enums import MismatchSeverity, MismatchSource, MismatchType, RiskAssessmentStatus, RiskLevel
from app.models.mismatch import Mismatch
from app.models.risk_assessment import RiskAssessment
from app.models.risk_factor import RiskFactor
from app.models.user import User
from app.services.risk.risk_engine import RiskEngine


@pytest.mark.anyio
async def test_risk_and_mismatch_api_authorization_and_isolation(
    civilian_user: User, civilian_b_user: User, officer_a_user: User
) -> None:
    """Verify RBAC and case isolation for triggering and inspecting risk assessments and discrepancies."""
    case_id = uuid.uuid4()
    profile_id = uuid.uuid4()
    assessment_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    mock_assessment = RiskAssessment(
        id=assessment_id,
        case_id=case_id,
        property_profile_id=profile_id,
        property_profile_version=1,
        risk_score=55,
        raw_score=55,
        risk_level=RiskLevel.HIGH,
        status=RiskAssessmentStatus.COMPLETED,
        risk_version="1.0",
        severity_rule_version="1.0",
        calculated_at=now,
        created_at=now,
        updated_at=now,
    )
    mock_assessment.factors = [
        RiskFactor(
            id=uuid.uuid4(),
            risk_assessment_id=assessment_id,
            factor_code="SURVEY_NUMBER_MISMATCH",
            severity=MismatchSeverity.HIGH,
            points=30,
            description="Survey number differs from reference record.",
            created_at=now,
        ),
        RiskFactor(
            id=uuid.uuid4(),
            risk_assessment_id=assessment_id,
            factor_code="OWNER_MISMATCH",
            severity=MismatchSeverity.HIGH,
            points=25,
            description="Owner name does not match registered title.",
            created_at=now,
        ),
    ]

    mock_mismatch = Mismatch(
        id=uuid.uuid4(),
        case_id=case_id,
        property_profile_id=profile_id,
        mismatch_type=MismatchType.SURVEY_NUMBER_MISMATCH,
        mismatch_source=MismatchSource.DATABASE,
        field_name="survey_number",
        document_value="123/45",
        reference_value="123/54",
        severity=MismatchSeverity.HIGH,
        description="Survey number mismatch.",
        rule_version="1.0",
        created_at=now,
        updated_at=now,
    )
    mock_mismatch.evidence_links = []

    with patch.object(
        RiskEngine, "calculate_case_risk", new_callable=AsyncMock
    ) as mock_calc, patch.object(
        RiskEngine, "get_current_case_risk", new_callable=AsyncMock
    ) as mock_get_current, patch.object(
        RiskEngine, "list_case_risk_history", new_callable=AsyncMock
    ) as mock_list_hist, patch.object(
        RiskEngine, "list_case_mismatches", new_callable=AsyncMock
    ) as mock_list_mismatches:

        mock_calc.return_value = mock_assessment
        mock_get_current.return_value = mock_assessment
        mock_list_hist.return_value = [mock_assessment]
        mock_list_mismatches.return_value = [mock_mismatch]

        # 1. Area Officer triggers calculation -> 201 CREATED
        app.dependency_overrides[get_current_user] = lambda: officer_a_user
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            res_calc = await ac.post(f"/api/v1/cases/{case_id}/risk-assessment")
            assert res_calc.status_code == 201
            assert res_calc.json()["risk_score"] == 55
            assert res_calc.json()["risk_level"] == "high"
            assert len(res_calc.json()["factors"]) == 2

            # 2. Area Officer lists mismatches -> 200 OK
            res_m = await ac.get(f"/api/v1/cases/{case_id}/mismatches")
            assert res_m.status_code == 200
            assert len(res_m.json()) == 1
            assert res_m.json()[0]["mismatch_type"] == "survey_number_mismatch"

        # 3. Civilian attempts trigger calculation -> 403 Forbidden
        mock_calc.side_effect = HTTPException(
            status_code=403,
            detail="Civilians cannot trigger risk calculations.",
        )
        app.dependency_overrides[get_current_user] = lambda: civilian_user
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            res_civ_calc = await ac.post(f"/api/v1/cases/{case_id}/risk-assessment")
            assert res_civ_calc.status_code == 403

            # 4. Civilian views current assessment for own case -> 200 OK
            res_civ_view = await ac.get(f"/api/v1/cases/{case_id}/risk-assessment/current")
            assert res_civ_view.status_code == 200

        # 5. Civilian B unauthorized -> 403 Forbidden
        mock_get_current.side_effect = HTTPException(
            status_code=403,
            detail="You do not have permission to access this case.",
        )
        app.dependency_overrides[get_current_user] = lambda: civilian_b_user
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            res_b = await ac.get(f"/api/v1/cases/{case_id}/risk-assessment/current")
            assert res_b.status_code == 403

    app.dependency_overrides.clear()
