from typing import Optional
from pydantic import BaseModel, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    """Public civilian user registration request schema."""

    full_name: str = Field(..., min_length=1, max_length=255, description="Full user name")
    email: EmailStr = Field(..., description="Valid email address")
    password: str = Field(..., min_length=8, max_length=128, description="Account password (min 8 chars)")
    phone: Optional[str] = Field(None, max_length=50, description="Optional phone number")

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Full name cannot be empty or whitespace only.")
        return trimmed

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: EmailStr) -> str:
        return str(v).strip().lower()

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v.strip()) < 8:
            raise ValueError("Password must be at least 8 characters long and not whitespace only.")
        return v


class LoginRequest(BaseModel):
    """User authentication login request schema."""

    email: EmailStr = Field(..., description="Registered email address")
    password: str = Field(..., min_length=1, description="Account password")

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: EmailStr) -> str:
        return str(v).strip().lower()


class TokenResponse(BaseModel):
    """JWT and refresh token response schema."""

    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="Opaque refresh token")
    token_type: str = Field(default="bearer", description="Token type identifier")
    expires_in: int = Field(..., description="Access token expiration lifespan in seconds")


class RefreshTokenRequest(BaseModel):
    """Token rotation refresh request schema."""

    refresh_token: str = Field(..., min_length=1, description="Current valid refresh token")


class LogoutRequest(BaseModel):
    """User session logout request schema."""

    refresh_token: str = Field(..., min_length=1, description="Refresh token to revoke")


class MessageResponse(BaseModel):
    """Generic informational message response."""

    message: str = Field(..., description="Operation status message")
