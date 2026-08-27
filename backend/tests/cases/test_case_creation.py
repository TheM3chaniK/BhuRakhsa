from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
import uuid

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
async def test_civilian_creates_case_success(
    civilian_user: User, area_a: Area
) -> None:
    """Verify civilian successfully creates a new verification case in DRAFT status."""
    now = datetime.now(timezone.utc)
    mock_case = Case(
        id=uuid.uuid4(),
        case_number="CASE-2026-000001",
        created_by=civilian_user.id,
        area_id=area_a.id,
        status=CaseStatus.DRAFT,
        risk_level=RiskLevel.UNKNOWN,
        title="Inherited Property Verification",
        description="Verification for residential plot",
        created_at=now,
        updated_at=now,
    )

    with patch.object(
        CaseService, "create_case", new_callable=AsyncMock
    ) as mock_create:
        mock_create.return_value = mock_case

        app.dependency_overrides[get_current_user] = lambda: civilian_user
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            res = await ac.post(
                "/api/v1/cases",
                json={
                    "area_id": str(area_a.id),
                    "title": "Inherited Property Verification",
                    "description": "Verification for residential plot",
                },
            )
            assert res.status_code == 201
            data = res.json()
            assert data["case_number"] == "CASE-2026-000001"
            assert data["status"] == "draft"
            assert data["risk_level"] == "unknown"
            assert data["created_by"] == str(civilian_user.id)
            assert data["area_id"] == str(area_a.id)

    app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_case_creation_rbac_restrictions(
    super_admin_user: User, officer_a_user: User, area_a: Area
) -> None:
    """Verify Area Officer and Super Admin are forbidden from creating civilian cases."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        payload = {"area_id": str(area_a.id), "title": "Test Case"}

        # 1. Super Admin -> 403 Forbidden
        app.dependency_overrides[get_current_user] = lambda: super_admin_user
        res_admin = await ac.post("/api/v1/cases", json=payload)
        assert res_admin.status_code == 403

        # 2. Area Officer -> 403 Forbidden
        app.dependency_overrides[get_current_user] = lambda: officer_a_user
        res_off = await ac.post("/api/v1/cases", json=payload)
        assert res_off.status_code == 403

    app.dependency_overrides.clear()
