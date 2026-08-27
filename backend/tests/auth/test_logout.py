from unittest.mock import AsyncMock, patch
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.auth_service import AuthService


@pytest.mark.anyio
async def test_logout_endpoint() -> None:
    """Verify that POST /auth/logout calls revoke_refresh_token and returns success."""
    with patch.object(
        AuthService, "revoke_refresh_token", new_callable=AsyncMock
    ) as mock_revoke:
        mock_revoke.return_value = None

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            res = await ac.post(
                "/api/v1/auth/logout",
                json={"refresh_token": "token-to-revoke"},
            )
            assert res.status_code == 200
            assert "Successfully logged out" in res.json()["message"]
            mock_revoke.assert_called_once()
