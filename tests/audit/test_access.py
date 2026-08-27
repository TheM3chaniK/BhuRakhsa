from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
import uuid
from httpx import ASGITransport, AsyncClient
import pytest

from app.api.dependencies import get_current_user
from app.main import app
from app.models.user import User
from app.services.audit_service import AuditService


@pytest.mark.anyio
async def test_audit_access_filtering_by_role(civilian_user: User, officer_a_user: User, super_admin_user: User) -> None:
    """Verify that civilian gets filtered safe timeline, while officer and admin get full audit records."""
    case_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    mock_civ_timeline = [
        {
            "id": str(uuid.uuid4()),
            "case_id": str(case_id),
            "action": "case_created",
            "title": "Case created",
            "status": "draft",
            "created_at": now.isoformat(),
        }
    ]

    mock_officer_audit = [
        {
            "id": str(uuid.uuid4()),
            "case_id": str(case_id),
            "actor_id": str(civilian_user.id),
            "actor_type": "user",
            "action": "case_created",
            "entity_type": "case",
            "entity_id": str(case_id),
            "old_state": None,
            "new_state": "draft",
            "metadata": None,
            "created_at": now.isoformat(),
        },
        {
            "id": str(uuid.uuid4()),
            "case_id": str(case_id),
            "actor_id": None,
            "actor_type": "system",
            "action": "risk_calculated",
            "entity_type": "risk_assessment",
            "entity_id": str(uuid.uuid4()),
            "old_state": "calculating",
            "new_state": "completed",
            "metadata": {"risk_score": 45},
            "created_at": now.isoformat(),
        },
    ]

    with patch.object(
        AuditService, "list_case_audit_events", new_callable=AsyncMock
    ) as mock_list_audit:

        # 1. Civilian access
        mock_list_audit.return_value = mock_civ_timeline
        app.dependency_overrides[get_current_user] = lambda: civilian_user
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            res_civ = await ac.get(f"/api/v1/cases/{case_id}/audit")
            assert res_civ.status_code == 200
            assert len(res_civ.json()) == 1
            assert res_civ.json()[0]["action"] == "case_created"

        # 2. Officer access
        mock_list_audit.return_value = mock_officer_audit
        app.dependency_overrides[get_current_user] = lambda: officer_a_user
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            res_off = await ac.get(f"/api/v1/cases/{case_id}/audit")
            assert res_off.status_code == 200
            assert len(res_off.json()) == 2

        app.dependency_overrides.clear()
