from datetime import datetime
from typing import List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.schemas.area import AreaResponse


class OfficerCreate(BaseModel):
    """Schema for Super Admin creating an Area Officer account."""

    full_name: str = Field(..., min_length=1, max_length=255, description="Full name of officer")
    email: EmailStr = Field(..., description="Official officer email address")
    password: str = Field(..., min_length=8, max_length=128, description="Temporary or initial password")
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
            raise ValueError("Password must be at least 8 characters long.")
        return v


class OfficerUpdate(BaseModel):
    """Schema for updating an Area Officer profile or activation status."""

    full_name: Optional[str] = Field(None, min_length=1, max_length=255, description="Officer name")
    phone: Optional[str] = Field(None, max_length=50, description="Contact phone")
    is_active: Optional[bool] = Field(None, description="Active/inactive status")

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            trimmed = v.strip()
            if not trimmed:
                raise ValueError("Full name cannot be empty or whitespace only.")
            return trimmed
        return v


class OfficerAssignmentResponse(BaseModel):
    """Response schema for an Area Officer assignment."""

    id: uuid.UUID = Field(..., description="Assignment identifier")
    officer_id: uuid.UUID = Field(..., description="Officer user UUID")
    area_id: uuid.UUID = Field(..., description="Assigned area UUID")
    created_at: datetime = Field(..., description="Assignment creation timestamp")

    model_config = ConfigDict(from_attributes=True)


class OfficerDetailResponse(BaseModel):
    """Detailed Area Officer profile with assigned geographical areas."""

    id: uuid.UUID = Field(..., description="Officer user identifier")
    full_name: str = Field(..., description="Full officer name")
    email: str = Field(..., description="Officer email address")
    phone: Optional[str] = Field(None, description="Contact phone number")
    role: str = Field(default="area_officer", description="User role")
    is_active: bool = Field(..., description="Active status flag")
    is_verified: bool = Field(..., description="Verification flag")
    created_at: datetime = Field(..., description="Account creation timestamp")
    last_login_at: Optional[datetime] = Field(None, description="Last login timestamp")
    areas: List[AreaResponse] = Field(default_factory=list, description="Assigned geographical areas")

    model_config = ConfigDict(from_attributes=True)


class AssignmentActionResponse(BaseModel):
    """Structured response for officer area assignment actions."""

    success: bool = Field(default=True, description="Action success indicator")
    officer_id: uuid.UUID = Field(..., description="Assigned officer UUID")
    area_id: uuid.UUID = Field(..., description="Assigned area UUID")
    message: str = Field(default="Officer assigned to area successfully.", description="Result message")


class ActionSuccessResponse(BaseModel):
    """Generic action success confirmation."""

    success: bool = Field(default=True, description="Action success indicator")
    message: str = Field(..., description="Result message")
