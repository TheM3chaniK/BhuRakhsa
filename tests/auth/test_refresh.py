from unittest.mock import AsyncMock, patch

from fastapi import HTTPException, status
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.auth import TokenResponse
from app.services.auth_service import AuthService


@pytest.mark.anyio
async def test_refresh_token_rotation_success() -> None:
    """Verify that POST /auth/refresh returns a fresh token pair."""
    mock_tokens = TokenResponse(
        access_token="new.access.jwt",
        refresh_token="new-rotated-refresh-token",
        token_type="bearer",
        expires_in=1800,
    )

    with patch.object(
        AuthService, "rotate_refresh_token", new_callable=AsyncMock
    ) as mock_rotate:
        mock_rotate.return_value = mock_tokens

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            res = await ac.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": "valid-current-refresh-token"},
            )
            assert res.status_code == 200
            data = res.json()
            assert data["access_token"] == "new.access.jwt"
            assert data["refresh_token"] == "new-rotated-refresh-token"


@pytest.mark.anyio
async def test_refresh_token_revoked_rejected() -> None:
    """Verify that POST /auth/refresh with invalid or revoked token returns 401."""
    with patch.object(
        AuthService, "rotate_refresh_token", new_callable=AsyncMock
    ) as mock_rotate:
        mock_rotate.side_effect = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked refresh token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            res = await ac.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": "non-existent-or-revoked-token"},
            )
            assert res.status_code == 401
            assert "Invalid or revoked" in res.json()["detail"]


@pytest.mark.anyio
async def test_refresh_token_expired_rejected() -> None:
    """Verify that POST /auth/refresh with expired token returns 401."""
    with patch.object(
        AuthService, "rotate_refresh_token", new_callable=AsyncMock
    ) as mock_rotate:
        mock_rotate.side_effect = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            res = await ac.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": "expired-token"},
            )
            assert res.status_code == 401
            assert "expired" in res.json()["detail"]
