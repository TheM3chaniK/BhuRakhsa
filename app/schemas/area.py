from datetime import datetime
from typing import Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AreaBase(BaseModel):
    """Base area attributes."""

    name: str = Field(..., min_length=1, max_length=255, description="Human-readable area name")
    code: str = Field(..., min_length=1, max_length=50, description="Unique area code (e.g. AREA-001)")
    description: Optional[str] = Field(None, description="Optional area description")

    @field_validator("code")
    @classmethod
    def normalize_code(cls, v: str) -> str:
        trimmed = v.strip().upper()
        if not trimmed:
            raise ValueError("Area code cannot be empty or whitespace only.")
        return trimmed

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Area name cannot be empty or whitespace only.")
        return trimmed


class AreaCreate(AreaBase):
    """Schema for administrative area creation."""
    pass


class AreaUpdate(BaseModel):
    """Schema for updating an existing area."""

    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Updated area name")
    description: Optional[str] = Field(None, description="Updated area description")
    is_active: Optional[bool] = Field(None, description="Active status flag")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            trimmed = v.strip()
            if not trimmed:
                raise ValueError("Area name cannot be empty or whitespace only.")
            return trimmed
        return v


class AreaResponse(BaseModel):
    """Public safe representation of a Geographical Area."""

    id: uuid.UUID = Field(..., description="Unique area identifier")
    name: str = Field(..., description="Human-readable area name")
    code: str = Field(..., description="Unique area code")
    description: Optional[str] = Field(None, description="Area description")
    is_active: bool = Field(..., description="Area active status")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    model_config = ConfigDict(from_attributes=True)


class OfficerAreaListResponse(BaseModel):
    """List of areas assigned to an officer."""

    areas: list[AreaResponse] = Field(..., description="List of assigned areas")
