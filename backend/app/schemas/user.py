from datetime import datetime
from typing import Optional
import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.enums import UserRole


class UserBase(BaseModel):
    """Base user attributes schema."""

    full_name: str = Field(..., min_length=1, max_length=255, description="Full legal name")
    email: EmailStr = Field(..., description="Unique email address")
    phone: Optional[str] = Field(None, max_length=50, description="Optional contact phone number")


class UserResponse(BaseModel):
    """Safe public user profile schema."""

    id: uuid.UUID = Field(..., description="Unique user identifier")
    full_name: str = Field(..., description="Full legal name")
    email: str = Field(..., description="Email address")
    phone: Optional[str] = Field(None, description="Contact phone number")
    role: UserRole = Field(..., description="Assigned user role")
    is_active: bool = Field(..., description="Account active status")
    is_verified: bool = Field(..., description="Identity verification status")
    created_at: datetime = Field(..., description="Account creation timestamp")
    updated_at: datetime = Field(..., description="Account last update timestamp")
    last_login_at: Optional[datetime] = Field(None, description="Last login timestamp")

    model_config = ConfigDict(from_attributes=True)


class UserProfileUpdate(BaseModel):
    """Schema for users updating their own basic profile attributes."""

    full_name: Optional[str] = Field(None, min_length=1, max_length=255, description="Updated full name")
    phone: Optional[str] = Field(None, max_length=50, description="Updated contact phone number")

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            trimmed = v.strip()
            if not trimmed:
                raise ValueError("Full name cannot be empty or whitespace only.")
            return trimmed
        return v


class ChangePasswordRequest(BaseModel):
    """Schema for authenticated password change."""

    current_password: str = Field(..., min_length=1, description="Current account password")
    new_password: str = Field(..., min_length=8, max_length=128, description="New secure password (min 8 chars)")

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        if len(v.strip()) < 8:
            raise ValueError("New password must be at least 8 characters long.")
        return v


class AdminUserUpdate(BaseModel):
    """Schema for Super Admin updating user profile and activation status."""

    full_name: Optional[str] = Field(None, min_length=1, max_length=255, description="Updated full name")
    phone: Optional[str] = Field(None, max_length=50, description="Updated phone number")
    is_active: Optional[bool] = Field(None, description="Active or suspended status")

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            trimmed = v.strip()
            if not trimmed:
                raise ValueError("Full name cannot be empty or whitespace only.")
            return trimmed
        return v
