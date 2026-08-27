from datetime import datetime, timezone
import uuid
from typing import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_current_user
from app.main import app
from app.models.area import Area
from app.models.enums import UserRole
from app.models.user import User


@pytest.fixture
def super_admin_user() -> User:
    """Fixture returning a mock Super Admin user."""
    now = datetime.now(timezone.utc)
    return User(
        id=uuid.uuid4(),
        full_name="System Super Admin",
        email="admin@example.com",
        password_hash="argon2_hashed_secret",
        role=UserRole.SUPER_ADMIN,
        is_active=True,
        is_verified=True,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def officer_a_user() -> User:
    """Fixture returning a mock Area Officer A."""
    now = datetime.now(timezone.utc)
    return User(
        id=uuid.uuid4(),
        full_name="Officer North",
        email="officer_a@example.com",
        password_hash="argon2_hashed_secret",
        role=UserRole.AREA_OFFICER,
        is_active=True,
        is_verified=True,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def officer_b_user() -> User:
    """Fixture returning a mock Area Officer B."""
    now = datetime.now(timezone.utc)
    return User(
        id=uuid.uuid4(),
        full_name="Officer South",
        email="officer_b@example.com",
        password_hash="argon2_hashed_secret",
        role=UserRole.AREA_OFFICER,
        is_active=True,
        is_verified=True,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def civilian_user() -> User:
    """Fixture returning a mock Civilian user."""
    now = datetime.now(timezone.utc)
    return User(
        id=uuid.uuid4(),
        full_name="Citizen User",
        email="citizen@example.com",
        password_hash="argon2_hashed_secret",
        role=UserRole.CIVILIAN,
        is_active=True,
        is_verified=True,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def area_a() -> Area:
    """Fixture returning a mock Area A."""
    now = datetime.now(timezone.utc)
    return Area(
        id=uuid.uuid4(),
        name="North District",
        code="AREA-NORTH",
        description="Northern administrative zone",
        is_active=True,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def area_b() -> Area:
    """Fixture returning a mock Area B."""
    now = datetime.now(timezone.utc)
    return Area(
        id=uuid.uuid4(),
        name="South District",
        code="AREA-SOUTH",
        description="Southern administrative zone",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
