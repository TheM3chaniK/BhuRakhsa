from datetime import datetime, timezone
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_current_user
from app.core.security import create_access_token
from app.main import app
from app.models.enums import UserRole
from app.models.user import User


@pytest.mark.anyio
async def test_get_me_missing_token_unauthorized() -> None:
    """Verify that accessing GET /auth/me without Authorization header returns 401."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        res = await ac.get("/api/v1/auth/me")
        assert res.status_code == 401


@pytest.mark.anyio
async def test_get_me_invalid_token_unauthorized() -> None:
    """Verify that accessing GET /auth/me with invalid token returns 401."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        res = await ac.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid.token.value"},
        )
        assert res.status_code == 401


@pytest.mark.anyio
async def test_get_me_valid_authenticated_user() -> None:
    """Verify that accessing GET /auth/me with a valid token returns the user profile."""
    mock_id = uuid.uuid4()
    mock_user = User(
        id=mock_id,
        full_name="Verified Civilian",
        email="civilian@example.com",
        phone="+919876543210",
        password_hash="argon2_hashed_secret",
        role=UserRole.CIVILIAN,
        is_active=True,
        is_verified=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        last_login_at=datetime.now(timezone.utc),
    )

    app.dependency_overrides[get_current_user] = lambda: mock_user
    try:
        token = create_access_token(subject=mock_id)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            res = await ac.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert res.status_code == 200
            data = res.json()
            assert data["id"] == str(mock_id)
            assert data["full_name"] == "Verified Civilian"
            assert data["email"] == "civilian@example.com"
            assert data["phone"] == "+919876543210"
            assert data["role"] == "civilian"
            assert data["is_active"] is True
            assert data["is_verified"] is True

            # Ensure sensitive fields are NEVER leaked
            assert "password_hash" not in data
            assert "refresh_tokens" not in data
            assert "token_hash" not in data
    finally:
        app.dependency_overrides.pop(get_current_user, None)
