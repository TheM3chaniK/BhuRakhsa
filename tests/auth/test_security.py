from datetime import timedelta
import uuid

import jwt
import pytest

from app.core.config import settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)


def test_password_hashing_and_verification() -> None:
    """Verify password hashing produces secure hashes and verifies correctly."""
    plain = "SuperSecretPassword123!"
    pwd_hash = hash_password(plain)

    assert pwd_hash != plain
    assert "$argon2id$" in pwd_hash
    assert verify_password(plain, pwd_hash) is True
    assert verify_password("WrongPassword123!", pwd_hash) is False
    assert verify_password("", pwd_hash) is False


def test_access_token_creation_and_decoding() -> None:
    """Verify JWT access token encoding, payload decoding, and claims."""
    user_id = uuid.uuid4()
    token = create_access_token(subject=user_id)

    payload = decode_access_token(token)
    assert payload["sub"] == str(user_id)
    assert payload["type"] == "access"
    assert "iat" in payload
    assert "exp" in payload
    assert payload["exp"] > payload["iat"]


def test_expired_access_token_decoding_fails() -> None:
    """Verify that decoding an expired JWT token raises ExpiredSignatureError."""
    user_id = uuid.uuid4()
    expired_token = create_access_token(
        subject=user_id, expires_delta=timedelta(seconds=-10)
    )

    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(expired_token)


def test_invalid_signature_token_fails() -> None:
    """Verify that decoding a token signed with a different secret fails."""
    user_id = uuid.uuid4()
    fake_token = jwt.encode(
        {"sub": str(user_id), "type": "access"},
        "wrong-secret-key-12345678901234567890",
        algorithm=settings.JWT_ALGORITHM,
    )

    with pytest.raises(jwt.InvalidSignatureError):
        decode_access_token(fake_token)


def test_refresh_token_generation_and_hashing() -> None:
    """Verify refresh token generation entropy and SHA-256 hashing."""
    token1 = generate_refresh_token()
    token2 = generate_refresh_token()

    assert token1 != token2
    assert len(token1) >= 40

    hash1 = hash_refresh_token(token1)
    hash2 = hash_refresh_token(token2)

    assert hash1 != hash2
    assert hash_refresh_token(token1) == hash1
    assert len(hash1) == 64  # SHA-256 hex length
