from datetime import datetime
from typing import Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import CaseStatus, RiskLevel


class CaseCreate(BaseModel):
    """Schema for civilian creating a new verification case."""

    area_id: uuid.UUID = Field(..., description="Geographical Area UUID")
    title: Optional[str] = Field(None, max_length=255, description="Short descriptive title for case")
    description: Optional[str] = Field(None, max_length=2000, description="Optional case details / remarks")

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            trimmed = v.strip()
            return trimmed if trimmed else None
        return v

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            trimmed = v.strip()
            return trimmed if trimmed else None
        return v


class CaseUpdate(BaseModel):
    """Schema for updating draft case details."""

    area_id: Optional[uuid.UUID] = Field(None, description="Updated Geographical Area UUID")
    title: Optional[str] = Field(None, max_length=255, description="Updated case title")
    description: Optional[str] = Field(None, max_length=2000, description="Updated case description")

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            trimmed = v.strip()
            return trimmed if trimmed else None
        return v

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            trimmed = v.strip()
            return trimmed if trimmed else None
        return v


class CaseResponse(BaseModel):
    """Detailed case representation."""

    id: uuid.UUID = Field(..., description="Unique case identifier")
    case_number: str = Field(..., description="Human-readable case identifier (e.g. CASE-2026-000001)")
    created_by: uuid.UUID = Field(..., description="Civilian creator UUID")
    area_id: uuid.UUID = Field(..., description="Assigned geographical area UUID")
    status: CaseStatus = Field(..., description="Current case status")
    risk_level: RiskLevel = Field(..., description="Assessed risk level")
    title: Optional[str] = Field(None, description="Case title")
    description: Optional[str] = Field(None, description="Case description")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    submitted_at: Optional[datetime] = Field(None, description="Submission timestamp")
    reviewed_at: Optional[datetime] = Field(None, description="Review timestamp")
    reviewed_by: Optional[uuid.UUID] = Field(None, description="Reviewing officer UUID")

    model_config = ConfigDict(from_attributes=True)


class CaseSubmissionResponse(BaseModel):
    """Response returned upon successful case submission."""

    id: uuid.UUID = Field(..., description="Case identifier")
    case_number: str = Field(..., description="Case number")
    status: CaseStatus = Field(..., description="New status (submitted)")
    risk_level: RiskLevel = Field(..., description="Risk level")
    submitted_at: datetime = Field(..., description="Submission timestamp")

    model_config = ConfigDict(from_attributes=True)
