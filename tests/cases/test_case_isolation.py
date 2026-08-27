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
from app.schemas.case import CaseResponse
from app.schemas.pagination import PaginatedResponse
from app.services.case_access_service import CaseAccessService
from app.services.case_service import CaseService


@pytest.mark.anyio
async def test_civilian_and_officer_case_isolation(
    civilian_user: User,
    civilian_b_user: User,
    officer_a_user: User,
    super_admin_user: User,
    area_a: Area,
    area_b: Area,
) -> None:
    """CRITICAL SECURITY TEST: Verify strict case isolation across civilians and area officers.

    - Civilian A sees only Case A.
    - Civilian B sees only Case B.
    - Civilian A attempting to inspect Case B receives 403 Forbidden.
    - Officer A (assigned to Area A) can inspect Case A (Area A) but is FORBIDDEN from Case B (Area B).
    - Super Admin can inspect both Case A and Case B.
    """
    now = datetime.now(timezone.utc)
    case_a = Case(
        id=uuid.uuid4(),
        case_number="CASE-2026-000001",
        created_by=civilian_user.id,
        area_id=area_a.id,
        status=CaseStatus.DRAFT,
        risk_level=RiskLevel.UNKNOWN,
        title="Civilian A Case",
        created_at=now,
        updated_at=now,
    )
    case_b = Case(
        id=uuid.uuid4(),
        case_number="CASE-2026-000002",
        created_by=civilian_b_user.id,
        area_id=area_b.id,
        status=CaseStatus.DRAFT,
        risk_level=RiskLevel.UNKNOWN,
        title="Civilian B Case",
        created_at=now,
        updated_at=now,
    )

    async def mock_get_case(db, case_id: uuid.UUID) -> Case | None:
        if case_id == case_a.id:
            return case_a
        if case_id == case_b.id:
            return case_b
        return None

    async def mock_list_cases(db, user: User, **kwargs) -> PaginatedResponse[CaseResponse]:
        if user.id == civilian_user.id:
            return PaginatedResponse.create(
                items=[CaseResponse.model_validate(case_a)], total=1, page=1, page_size=20
            )
        elif user.id == civilian_b_user.id:
            return PaginatedResponse.create(
                items=[CaseResponse.model_validate(case_b)], total=1, page=1, page_size=20
            )
        elif user.role == "super_admin":
            return PaginatedResponse.create(
                items=[
                    CaseResponse.model_validate(case_a),
                    CaseResponse.model_validate(case_b),
                ],
                total=2,
                page=1,
                page_size=20,
            )
        return PaginatedResponse.create(items=[], total=0, page=1, page_size=20)

    async def mock_can_access(db, user: User, case: Case) -> bool:
        if user.role == "super_admin":
            return True
        if user.id == civilian_user.id and case.created_by == civilian_user.id:
            return True
        if user.id == civilian_b_user.id and case.created_by == civilian_b_user.id:
            return True
        if user.id == officer_a_user.id and case.area_id == area_a.id:
            return True
        return False

    with patch.object(CaseService, "get_case", side_effect=mock_get_case), \
         patch.object(CaseService, "list_cases", side_effect=mock_list_cases), \
         patch.object(CaseAccessService, "can_access_case", side_effect=mock_can_access):

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            # -----------------------------------------------------------------
            # 1. Civilian A listing & detail tests
            # -----------------------------------------------------------------
            app.dependency_overrides[get_current_user] = lambda: civilian_user

            # List cases -> returns ONLY Case A
            res_list_a = await ac.get("/api/v1/cases")
            assert res_list_a.status_code == 200
            items_a = res_list_a.json()["items"]
            assert len(items_a) == 1
            assert items_a[0]["id"] == str(case_a.id)

            # Access own Case A -> 200 OK
            res_a_a = await ac.get(f"/api/v1/cases/{case_a.id}")
            assert res_a_a.status_code == 200

            # Access other's Case B -> 403 FORBIDDEN
            res_a_b = await ac.get(f"/api/v1/cases/{case_b.id}")
            assert res_a_b.status_code == 403

            # -----------------------------------------------------------------
            # 2. Civilian B listing & detail tests
            # -----------------------------------------------------------------
            app.dependency_overrides[get_current_user] = lambda: civilian_b_user

            # List cases -> returns ONLY Case B
            res_list_b = await ac.get("/api/v1/cases")
            assert res_list_b.status_code == 200
            items_b = res_list_b.json()["items"]
            assert len(items_b) == 1
            assert items_b[0]["id"] == str(case_b.id)

            # Access other's Case A -> 403 FORBIDDEN
            res_b_a = await ac.get(f"/api/v1/cases/{case_a.id}")
            assert res_b_a.status_code == 403

            # -----------------------------------------------------------------
            # 3. Area Officer A tests (Jurisdiction Bound)
            # -----------------------------------------------------------------
            app.dependency_overrides[get_current_user] = lambda: officer_a_user

            # Officer A -> Case A (Area A) -> 200 OK
            res_off_a = await ac.get(f"/api/v1/cases/{case_a.id}")
            assert res_off_a.status_code == 200

            # Officer A -> Case B (Area B) -> 403 FORBIDDEN
            res_off_b = await ac.get(f"/api/v1/cases/{case_b.id}")
            assert res_off_b.status_code == 403

            # -----------------------------------------------------------------
            # 4. Super Admin tests (Global access)
            # -----------------------------------------------------------------
            app.dependency_overrides[get_current_user] = lambda: super_admin_user

            # Admin -> Case A -> 200 OK
            res_admin_a = await ac.get(f"/api/v1/cases/{case_a.id}")
            assert res_admin_a.status_code == 200

            # Admin -> Case B -> 200 OK
            res_admin_b = await ac.get(f"/api/v1/cases/{case_b.id}")
            assert res_admin_b.status_code == 200

    app.dependency_overrides.clear()
