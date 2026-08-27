from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
import uuid

from fastapi import HTTPException, status
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import hash_password
from app.main import app
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse
from app.services.auth_service import AuthService
from tests.database.conftest import check_db_connectivity


@pytest.mark.anyio
async def test_login_successful_flow() -> None:
    """Verify that successful login returns access and refresh tokens."""
    mock_user = User(
        id=uuid.uuid4(),
        full_name="Valid User",
        email="valid@example.com",
        password_hash=hash_password("ValidPassword123!"),
        role=UserRole.CIVILIAN,
        is_active=True,
        is_verified=False,
    )
    mock_tokens = TokenResponse(
        access_token="fake.access.jwt",
        refresh_token="fake-raw-refresh-token",
        token_type="bearer",
        expires_in=1800,
    )

    with patch.object(
        AuthService, "authenticate_user", new_callable=AsyncMock
    ) as mock_auth, patch.object(
        AuthService, "create_tokens_for_user", new_callable=AsyncMock
    ) as mock_create_tokens:
        mock_auth.return_value = mock_user
        mock_create_tokens.return_value = mock_tokens

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            res = await ac.post(
                "/api/v1/auth/login",
                json={"email": "valid@example.com", "password": "ValidPassword123!"},
            )
            assert res.status_code == 200
            data = res.json()
            assert data["access_token"] == "fake.access.jwt"
            assert data["refresh_token"] == "fake-raw-refresh-token"
            assert data["token_type"] == "bearer"
            assert data["expires_in"] == 1800


@pytest.mark.anyio
async def test_login_invalid_password_returns_401() -> None:
    """Verify that invalid password returns 401 with generic error."""
    with patch.object(
        AuthService, "authenticate_user", new_callable=AsyncMock
    ) as mock_auth:
        mock_auth.side_effect = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            res = await ac.post(
                "/api/v1/auth/login",
                json={"email": "unknown@example.com", "password": "WrongPassword123!"},
            )
            assert res.status_code == 401
            assert "Invalid email or password" in res.json()["detail"]


@pytest.mark.anyio
async def test_login_inactive_user_returns_401() -> None:
    """Verify that inactive user login returns 401."""
    with patch.object(
        AuthService, "authenticate_user", new_callable=AsyncMock
    ) as mock_auth:
        mock_auth.side_effect = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive.",
            headers={"WWW-Authenticate": "Bearer"},
        )

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            res = await ac.post(
                "/api/v1/auth/login",
                json={"email": "inactive@example.com", "password": "ValidPassword123!"},
            )
            assert res.status_code == 401
            assert "inactive" in res.json()["detail"]
