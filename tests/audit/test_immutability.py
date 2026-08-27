import uuid
from httpx import ASGITransport, AsyncClient
import pytest

from app.api.dependencies import get_current_user
from app.main import app
from app.models.user import User


@pytest.mark.anyio
async def test_audit_events_endpoint_immutability(super_admin_user: User) -> None:
    """Verify that there are no PATCH or DELETE routes exposed for audit events."""
    app.dependency_overrides[get_current_user] = lambda: super_admin_user
    fake_id = uuid.uuid4()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Attempt PATCH -> 405 Method Not Allowed
        patch_res = await ac.patch(f"/api/v1/cases/{fake_id}/audit")
        assert patch_res.status_code in (404, 405)

        # Attempt DELETE -> 405 Method Not Allowed
        del_res = await ac.delete(f"/api/v1/cases/{fake_id}/audit")
        assert del_res.status_code in (404, 405)

    app.dependency_overrides.clear()
