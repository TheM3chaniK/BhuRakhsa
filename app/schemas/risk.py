from datetime import datetime
from typing import List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    MismatchSeverity,
    MismatchSource,
    MismatchType,
    RiskAssessmentStatus,
    RiskLevel,
)


class MismatchEvidenceResponse(BaseModel):
    """Evidence linkage for an identified discrepancy."""

    id: uuid.UUID = Field(..., description="Evidence link UUID")
    extracted_field_id: Optional[uuid.UUID] = Field(None, description="Linked extracted document field UUID")
    validation_result_id: Optional[uuid.UUID] = Field(None, description="Linked external validation outcome UUID")
    evidence_id: Optional[uuid.UUID] = Field(None, description="Linked OCR page grounding evidence UUID")

    model_config = ConfigDict(from_attributes=True)


class MismatchResponse(BaseModel):
    """Normalized discrepancy entity response."""

    id: uuid.UUID = Field(..., description="Mismatch record UUID")
    case_id: uuid.UUID = Field(..., description="Associated case UUID")
    property_profile_id: uuid.UUID = Field(..., description="Associated property profile UUID")
    validation_run_id: Optional[uuid.UUID] = Field(None, description="Validation run producing this discrepancy")
    mismatch_type: MismatchType = Field(..., description="Canonical discrepancy classification")
    mismatch_source: MismatchSource = Field(..., description="Pipeline origin ('database', 'gis', 'extraction')")
    field_name: Optional[str] = Field(None, description="Impacted property field")
    document_value: Optional[str] = Field(None, description="Document extracted value")
    reference_value: Optional[str] = Field(None, description="Authoritative reference value")
    severity: MismatchSeverity = Field(..., description="Assessed severity tier ('low', 'medium', 'high', 'critical')")
    description: str = Field(..., description="Human-readable explanation of discrepancy")
    rule_version: str = Field(..., description="Severity rule set version")
    created_at: datetime = Field(..., description="Discrepancy detection timestamp")
    evidence_links: List[MismatchEvidenceResponse] = Field(default_factory=list, description="Linked evidence chains")

    model_config = ConfigDict(from_attributes=True)


class RiskFactorResponse(BaseModel):
    """Explainable risk factor contribution schema."""

    id: uuid.UUID = Field(..., description="Risk factor UUID")
    factor_code: str = Field(..., description="Taxonomy identifier code")
    severity: MismatchSeverity = Field(..., description="Severity tier")
    points: int = Field(..., description="Assigned risk point contribution")
    description: str = Field(..., description="Plain-language explanation of risk contribution")

    model_config = ConfigDict(from_attributes=True)


class RiskAssessmentResponse(BaseModel):
    """Deterministic risk assessment output and review priority classification schema."""

    id: uuid.UUID = Field(..., description="Risk assessment UUID")
    case_id: uuid.UUID = Field(..., description="Case UUID")
    property_profile_id: uuid.UUID = Field(..., description="Property profile UUID")
    property_profile_version: int = Field(..., description="Property profile snapshot version")
    risk_score: int = Field(..., description="Final capped risk score between 0 and 100")
    raw_score: int = Field(..., description="Uncapped sum of risk factor points")
    risk_level: RiskLevel = Field(..., description="Review priority tier ('low', 'medium', 'high', 'critical')")
    status: RiskAssessmentStatus = Field(..., description="Calculation execution status ('completed', 'failed')")
    risk_version: str = Field(..., description="Risk scoring rule set version")
    severity_rule_version: str = Field(..., description="Severity rule set version")
    calculated_at: datetime = Field(..., description="Calculation timestamp")
    factors: List[RiskFactorResponse] = Field(default_factory=list, description="Traceable risk factor breakdown")

    model_config = ConfigDict(from_attributes=True)
