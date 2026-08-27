from datetime import datetime
from typing import List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import OwnershipType, ProfileStatus


class PropertyOwnerResponse(BaseModel):
    """Property owner entity response schema."""

    id: uuid.UUID = Field(..., description="Unique owner record ID")
    name: str = Field(..., description="Full legal name of the property owner")
    normalized_name: Optional[str] = Field(None, description="Normalized representation of the name")
    ownership_type: OwnershipType = Field(..., description="Ownership category (individual, joint, etc.)")
    share: Optional[str] = Field(None, description="Ownership share fractional or percentage representation")
    share_unit: Optional[str] = Field(None, description="Ownership share unit")
    created_at: datetime = Field(..., description="Record creation timestamp")

    model_config = ConfigDict(from_attributes=True)


class PropertyFieldSourceResponse(BaseModel):
    """Evidence traceability link tying a canonical profile attribute to an extracted source field."""

    id: uuid.UUID = Field(..., description="Traceability link UUID")
    field_name: str = Field(..., description="Canonical field identifier")
    extracted_field_id: uuid.UUID = Field(..., description="Source extracted field UUID")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Extraction confidence score")
    created_at: datetime = Field(..., description="Link creation timestamp")

    model_config = ConfigDict(from_attributes=True)


class PropertyFieldConflictResponse(BaseModel):
    """Conflict record for diverging values extracted across documents."""

    id: uuid.UUID = Field(..., description="Conflict record UUID")
    field_name: str = Field(..., description="Conflicting field identifier")
    value_a: str = Field(..., description="First extracted value")
    value_b: str = Field(..., description="Second extracted value")
    source_a: Optional[str] = Field(None, description="Source context for value A")
    source_b: Optional[str] = Field(None, description="Source context for value B")
    created_at: datetime = Field(..., description="Conflict detection timestamp")

    model_config = ConfigDict(from_attributes=True)


class PropertyProfileResponse(BaseModel):
    """Canonical property / parcel profile representation."""

    id: uuid.UUID = Field(..., description="Canonical property profile UUID")
    case_id: uuid.UUID = Field(..., description="Associated case UUID")
    status: ProfileStatus = Field(..., description="Current profile lifecycle status")

    # Identifiers
    property_identifier: Optional[str] = Field(None, description="Primary composite property identifier")
    survey_number: Optional[str] = Field(None, description="Cadastral survey number")
    plot_number: Optional[str] = Field(None, description="Plot number")
    parcel_number: Optional[str] = Field(None, description="Land parcel number")
    registration_number: Optional[str] = Field(None, description="Deed registration number")
    deed_number: Optional[str] = Field(None, description="Title deed number")

    # Location & Jurisdiction
    property_address: Optional[str] = Field(None, description="Full property address")
    district: Optional[str] = Field(None, description="District name")
    subdivision: Optional[str] = Field(None, description="Subdivision / Taluka")
    village: Optional[str] = Field(None, description="Village / Town")
    mouza: Optional[str] = Field(None, description="Revenue mouza")
    ward: Optional[str] = Field(None, description="Municipal ward")

    # Physical Area
    property_area: Optional[float] = Field(None, description="Total property area numeric extent")
    area_unit: Optional[str] = Field(None, description="Area measurement unit (acres, sq ft, etc.)")

    # Spatial Coordinates
    latitude: Optional[float] = Field(None, description="Latitude coordinate if known")
    longitude: Optional[float] = Field(None, description="Longitude coordinate if known")

    # Linked Entities
    owners: List[PropertyOwnerResponse] = Field(default_factory=list, description="Property owners")
    field_sources: List[PropertyFieldSourceResponse] = Field(default_factory=list, description="Field-to-extraction links")
    conflicts: List[PropertyFieldConflictResponse] = Field(default_factory=list, description="Field conflicts if any")

    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    model_config = ConfigDict(from_attributes=True)
