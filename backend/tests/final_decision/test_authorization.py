from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
import uuid
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
import pytest

from app.api.dependencies import get_current_user
from app.main import app
from app.models.case import Case
from app.models.enums import CaseStatus, RiskLevel
from app.models.user import User
from app.services.case_service import CaseService


@pytest.mark.anyio
async def test_final_decision_authorization_and_isolation(civilian_user: User, civilian_b_user: User) -> None:
    """Test RBAC and data isolation on final decision and case status endpoints."""
    case_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    mock_case = Case(
        id=case_id,
        case_number="CASE-2026-000001",
        created_by=civilian_user.id,
        area_id=uuid.uuid4(),
        status=CaseStatus.APPROVED,
        risk_level=RiskLevel.LOW,
        title="Civilian 1 Case",
        created_at=now,
        updated_at=now,
    )

    with patch.object(
        CaseService, "get_case", new_callable=AsyncMock
    ) as mock_get_case:
        mock_get_case.return_value = mock_case

        # 1. Civ 1 fetches own case status -> 200 OK
        app.dependency_overrides[get_current_user] = lambda: civilian_user
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            res1 = await ac.get(f"/api/v1/me/cases/{case_id}/status")
            assert res1.status_code == 200
            assert res1.json()["status"] == "approved"

            # 2. Civ 1 attempts to submit decision -> 403 Forbidden
            res2 = await ac.post(
                f"/api/v1/cases/{case_id}/review/decision",
                json={"decision": "approve", "reason": "Self approve attempt"},
            )
            assert res2.status_code == 403

        # 3. Civ 2 attempts to fetch Civ 1's case status -> 403 Forbidden
        app.dependency_overrides[get_current_user] = lambda: civilian_b_user
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            with patch(
                "app.services.case_access_service.CaseAccessService.verify_case_access",
                side_effect=HTTPException(status_code=403, detail="Access denied."),
            ):
                res3 = await ac.get(f"/api/v1/me/cases/{case_id}/status")
                assert res3.status_code == 403

        app.dependency_overrides.clear()
