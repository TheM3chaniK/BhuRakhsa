from datetime import datetime
from typing import List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class ReferenceOwnerResponse(BaseModel):
    """Authoritative owner record response schema."""

    id: uuid.UUID = Field(..., description="Unique reference owner UUID")
    name: str = Field(..., description="Full registered owner name")
    normalized_name: str = Field(..., description="Normalized lookup representation of owner name")
    ownership_share: Optional[str] = Field(None, description="Registered fractional or percentage share")

    model_config = ConfigDict(from_attributes=True)


class ReferencePropertyResponse(BaseModel):
    """Authoritative reference property entity response schema."""

    id: uuid.UUID = Field(..., description="Internal reference property UUID")
    source_id: str = Field(..., description="Authority / registry source identifier")
    source_record_id: str = Field(..., description="External unique record identifier in registry")

    # Identifiers
    survey_number: Optional[str] = Field(None, description="Cadastral survey number")
    plot_number: Optional[str] = Field(None, description="Plot number")
    parcel_number: Optional[str] = Field(None, description="Land parcel number")
    registration_number: Optional[str] = Field(None, description="Registration deed number")
    deed_number: Optional[str] = Field(None, description="Deed instrument number")

    # Location
    property_address: Optional[str] = Field(None, description="Physical location address")
    district: Optional[str] = Field(None, description="District name")
    subdivision: Optional[str] = Field(None, description="Subdivision / Taluka")
    village: Optional[str] = Field(None, description="Village name")
    mouza: Optional[str] = Field(None, description="Revenue mouza")
    ward: Optional[str] = Field(None, description="Municipal ward")

    # Area
    property_area: Optional[float] = Field(None, description="Total property extent")
    area_unit: Optional[str] = Field(None, description="Area measurement unit")

    dataset_version: str = Field(..., description="Reference snapshot dataset version")
    owners: List[ReferenceOwnerResponse] = Field(default_factory=list, description="Registered owners")

    created_at: datetime = Field(..., description="Record insertion timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    model_config = ConfigDict(from_attributes=True)


class ReferenceImportResponse(BaseModel):
    """Summary metrics of reference dataset import session."""

    total_records: int = Field(..., description="Total rows parsed from import file")
    inserted: int = Field(..., description="Number of new records inserted")
    updated: int = Field(..., description="Number of existing records updated (upsert)")
    failed: int = Field(default=0, description="Number of invalid records discarded")
