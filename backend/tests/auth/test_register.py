from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from app.main import app
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.auth import RegisterRequest
from app.services.auth_service import AuthService
from tests.database.conftest import check_db_connectivity


def test_register_request_schema_validation() -> None:
    """Verify input validation rules on RegisterRequest schema."""
    # Valid
    req = RegisterRequest(
        full_name="John Doe",
        email="John.Doe@Example.com",
        password="SecurePassword123!",
        phone="+919876543210",
    )
    assert req.email == "john.doe@example.com"
    assert req.full_name == "John Doe"

    # Short password
    with pytest.raises(ValidationError):
        RegisterRequest(
            full_name="John Doe",
            email="john@example.com",
            password="short",
        )

    # Invalid email
    with pytest.raises(ValidationError):
        RegisterRequest(
            full_name="John Doe",
            email="invalid-email-address",
            password="SecurePassword123!",
        )

    # Empty name
    with pytest.raises(ValidationError):
        RegisterRequest(
            full_name="   ",
            email="john@example.com",
            password="SecurePassword123!",
        )


@pytest.mark.anyio
async def test_register_endpoint_validation_errors() -> None:
    """Verify endpoint returns 422 for invalid payloads."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        # Invalid email
        res1 = await ac.post(
            "/api/v1/auth/register",
            json={"full_name": "Test", "email": "bad", "password": "password123"},
        )
        assert res1.status_code == 422

        # Short password
        res2 = await ac.post(
            "/api/v1/auth/register",
            json={"full_name": "Test", "email": "test@example.com", "password": "123"},
        )
        assert res2.status_code == 422


@pytest.mark.anyio
async def test_register_ignores_client_supplied_role() -> None:
    """Verify that public registration always produces a CIVILIAN user even if role is sent."""
    now = datetime.now(timezone.utc)
    mock_user = User(
        id=uuid.uuid4(),
        full_name="Alice Officer",
        email="alice@example.com",
        phone="+919999999999",
        password_hash="argon2_hashed_value",
        role=UserRole.CIVILIAN,  # Always CIVILIAN
        is_active=True,
        is_verified=False,
        created_at=now,
        updated_at=now,
        last_login_at=None,
    )

    with patch.object(AuthService, "register_user", new_callable=AsyncMock) as mock_reg:
        mock_reg.return_value = mock_user

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            res = await ac.post(
                "/api/v1/auth/register",
                json={
                    "full_name": "Alice Officer",
                    "email": "alice@example.com",
                    "phone": "+919999999999",
                    "password": "SecurePassword123!",
                    "role": "super_admin",  # Client tries to escalate role
                },
            )
            assert res.status_code == 201
            data = res.json()
            assert data["role"] == "civilian"
            assert "password_hash" not in data


@pytest.mark.anyio
async def test_register_duplicate_email_conflict() -> None:
    """Verify that duplicate email registration returns 409 Conflict."""
    if not await check_db_connectivity():
        pytest.skip("Live database not available for duplicate check")

    unique_email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    payload = {
        "full_name": "Duplicate Test User",
        "email": unique_email,
        "password": "Password123!",
    }

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        # First registration
        res1 = await ac.post("/api/v1/auth/register", json=payload)
        assert res1.status_code == 201

        # Duplicate registration attempt
        res2 = await ac.post("/api/v1/auth/register", json=payload)
        assert res2.status_code == 409
        assert "already exists" in res2.json()["detail"]
