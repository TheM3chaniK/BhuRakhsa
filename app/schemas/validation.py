from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    CandidateSelectionStatus,
    MatchStatus,
    ValidationStatus,
    ValidationType,
)


class ValidationRunCreate(BaseModel):
    """Payload for scheduling an external validation run."""

    validation_type: ValidationType = Field(..., description="Type of validation to trigger ('database' or 'gis')")


class ValidationCandidateResponse(BaseModel):
    """Candidate reference property matched during search."""

    id: uuid.UUID = Field(..., description="Candidate record UUID")
    source_id: str = Field(..., description="Authority source identifier")
    source_record_id: str = Field(..., description="Registry record identifier")
    match_score: float = Field(..., description="Confidence ranking match score")
    selection_status: CandidateSelectionStatus = Field(..., description="Resolution status ('selected', 'rejected', 'ambiguous')")
    created_at: datetime = Field(..., description="Timestamp of ranking evaluation")

    model_config = ConfigDict(from_attributes=True)


class ValidationResultResponse(BaseModel):
    """Field comparison result against reference registry."""

    id: uuid.UUID = Field(..., description="Validation result UUID")
    validation_run_id: uuid.UUID = Field(..., description="Parent validation run UUID")
    field_name: str = Field(..., description="Evaluated field name")
    document_value: Optional[str] = Field(None, description="Value extracted from document")
    reference_value: Optional[str] = Field(None, description="Value found in government reference registry")
    match_status: MatchStatus = Field(..., description="Comparison outcome ('match', 'partial_match', 'mismatch', 'not_found', 'not_checked')")
    match_score: Optional[float] = Field(default=0.0, description="Field alignment score between 0.0 and 1.0")
    mismatch_reason: Optional[str] = Field(None, description="Explanation code for discrepancy if present")
    source_id: Optional[str] = Field(None, description="Authoritative source ID")
    source_record_id: Optional[str] = Field(None, description="Authoritative record ID")

    # Spatial / GIS measurement fields
    geometry_distance_meters: Optional[float] = Field(None, description="Distance from point to parcel boundary in meters")
    geometry_area: Optional[float] = Field(None, description="Calculated polygon surface area in square meters")
    reference_area: Optional[float] = Field(None, description="Reference stated area in square meters")
    coordinate_latitude: Optional[float] = Field(None, description="Evaluated latitude")
    coordinate_longitude: Optional[float] = Field(None, description="Evaluated longitude")

    created_at: datetime = Field(..., description="Result timestamp")

    model_config = ConfigDict(from_attributes=True)


class ValidationRunResponse(BaseModel):
    """Validation run summary response."""

    id: uuid.UUID = Field(..., description="Validation run UUID")
    property_profile_id: uuid.UUID = Field(..., description="Target property profile UUID")
    validation_type: ValidationType = Field(..., description="Validation category ('database' or 'gis')")
    status: ValidationStatus = Field(..., description="Execution status ('pending', 'running', 'passed', 'failed', 'passed_with_limitations')")
    source_id: Optional[str] = Field(None, description="Matched reference authority identifier")
    dataset_version: Optional[str] = Field(None, description="Reference dataset version")
    validator_version: Optional[str] = Field(default="1.0", description="Validation engine pipeline version")
    started_at: Optional[datetime] = Field(None, description="Run commencement timestamp")
    completed_at: Optional[datetime] = Field(None, description="Run completion timestamp")
    created_at: datetime = Field(..., description="Run creation timestamp")

    model_config = ConfigDict(from_attributes=True)


class ValidationRunDetailResponse(ValidationRunResponse):
    """Detailed validation run with candidates and individual field match results."""

    candidates: List[ValidationCandidateResponse] = Field(default_factory=list, description="Evaluated candidate matches")
    results: List[ValidationResultResponse] = Field(default_factory=list, description="Field validation results")

    model_config = ConfigDict(from_attributes=True)


class GISCheckResult(BaseModel):
    """Structured individual GIS check outcome."""

    check: str = Field(..., description="Identifier name of spatial check")
    status: MatchStatus = Field(..., description="Check status ('match', 'mismatch', 'not_found', 'not_checked')")
    distance_meters: Optional[float] = Field(None, description="Distance from point to parcel boundary in meters")
    geometry_area: Optional[float] = Field(None, description="Calculated GIS surface area in square meters")
    reference_area: Optional[float] = Field(None, description="Declared reference area in square meters")
    mismatch_reason: Optional[str] = Field(None, description="Discrepancy explanation code")


class GISValidationRunResponse(BaseModel):
    """Summary of GIS validation session checks."""

    validation_run_id: uuid.UUID = Field(..., description="Validation run UUID")
    status: ValidationStatus = Field(..., description="Overall GIS validation status")
    checks: List[GISCheckResult] = Field(default_factory=list, description="List of spatial check outcomes")


class CaseMapDataResponse(BaseModel):
    """Authorized spatial map layers for a case."""

    case_id: uuid.UUID = Field(..., description="Case UUID")
    property_identifier: Optional[str] = Field(None, description="Composite canonical property identifier")
    property_point: Optional[Dict[str, Any]] = Field(None, description="GeoJSON Point feature of property location")
    reference_parcel: Optional[Dict[str, Any]] = Field(None, description="GeoJSON MultiPolygon feature of reference parcel")
    gis_validation_status: str = Field(..., description="Latest GIS validation status ('passed', 'failed', 'not_run')")
