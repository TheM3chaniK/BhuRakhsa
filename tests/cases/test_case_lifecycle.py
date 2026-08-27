from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
import uuid

from fastapi import HTTPException
import pytest
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_current_user
from app.main import app
from app.models.area import Area
from app.models.case import Case
from app.models.enums import CaseStatus, RiskLevel
from app.models.user import User
from app.services.case_service import CaseService


@pytest.mark.anyio
async def test_case_lifecycle_draft_to_submitted(
    civilian_user: User, civilian_b_user: User, area_a: Area
) -> None:
    """Verify case lifecycle: update draft, submit, immutability of submitted case."""
    now = datetime.now(timezone.utc)
    draft_case = Case(
        id=uuid.uuid4(),
        case_number="CASE-2026-000001",
        created_by=civilian_user.id,
        area_id=area_a.id,
        status=CaseStatus.DRAFT,
        risk_level=RiskLevel.UNKNOWN,
        title="Initial Draft Title",
        description="Initial description",
        created_at=now,
        updated_at=now,
    )
    submitted_case = Case(
        id=draft_case.id,
        case_number=draft_case.case_number,
        created_by=civilian_user.id,
        area_id=area_a.id,
        status=CaseStatus.SUBMITTED,
        risk_level=RiskLevel.UNKNOWN,
        title="Updated Title",
        description="Updated description",
        created_at=now,
        updated_at=now,
        submitted_at=now,
    )

    with patch.object(CaseService, "update_case", new_callable=AsyncMock) as mock_upd, \
         patch.object(CaseService, "submit_case", new_callable=AsyncMock) as mock_sub:

        mock_upd.return_value = submitted_case
        mock_sub.return_value = submitted_case

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            case_id = str(draft_case.id)

            # 1. Update draft case -> 200 OK
            app.dependency_overrides[get_current_user] = lambda: civilian_user
            res_upd = await ac.patch(
                f"/api/v1/cases/{case_id}",
                json={"title": "Updated Title", "description": "Updated description"},
            )
            assert res_upd.status_code == 200
            assert res_upd.json()["title"] == "Updated Title"

            # 2. Submit case -> 200 OK
            res_sub = await ac.post(f"/api/v1/cases/{case_id}/submit")
            assert res_sub.status_code == 200
            assert res_sub.json()["status"] == "submitted"
            assert res_sub.json()["submitted_at"] is not None

            # 3. Attempt update on submitted case -> 409 Conflict
            mock_upd.side_effect = HTTPException(
                status_code=409,
                detail="Submitted or processed cases cannot be modified.",
            )
            res_upd_after = await ac.patch(
                f"/api/v1/cases/{case_id}",
                json={"title": "Trying to modify submitted"},
            )
            assert res_upd_after.status_code == 409

            # 4. Attempt to re-submit submitted case -> 409 Conflict
            mock_sub.side_effect = HTTPException(
                status_code=409,
                detail="Case has already been submitted or is not in draft status.",
            )
            res_sub_twice = await ac.post(f"/api/v1/cases/{case_id}/submit")
            assert res_sub_twice.status_code == 409

            # 5. Other civilian trying to submit someone else's case -> 403 Forbidden
            mock_sub.side_effect = HTTPException(
                status_code=403,
                detail="Only the case owner can submit this case.",
            )
            app.dependency_overrides[get_current_user] = lambda: civilian_b_user
            res_sub_other = await ac.post(f"/api/v1/cases/{case_id}/submit")
            assert res_sub_other.status_code == 403

    app.dependency_overrides.clear()
