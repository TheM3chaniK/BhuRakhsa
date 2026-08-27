from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    CaseStatus,
    OfficerDecision,
    ReviewAction,
    ReviewStatus,
    RiskLevel,
)
from app.schemas.case import CaseResponse
from app.schemas.document import DocumentResponse
from app.schemas.property_profile import PropertyProfileResponse
from app.schemas.risk import MismatchResponse, RiskAssessmentResponse
from app.schemas.validation import ValidationRunDetailResponse


class ReviewQueueItemResponse(BaseModel):
    """Single review candidate item in the Area Officer verification queue."""

    case_id: uuid.UUID = Field(..., description="Case UUID")
    case_number: str = Field(..., description="Consecutive case tracking number")
    title: Optional[str] = Field(None, description="Case title")
    area_id: uuid.UUID = Field(..., description="Assigned geographical area UUID")
    risk_score: int = Field(..., description="Capped risk score (0-100)")
    risk_level: RiskLevel = Field(..., description="Review priority tier")
    case_status: CaseStatus = Field(..., description="Current case status")
    review_status: ReviewStatus = Field(..., description="Current review status")
    reviewer_id: Optional[uuid.UUID] = Field(None, description="Assigned reviewing officer UUID if in progress")
    created_at: datetime = Field(..., description="Case submission/creation timestamp")

    model_config = ConfigDict(from_attributes=True)


class ReviewQueueResponse(BaseModel):
    """Paginated list of review-ready cases for an Area Officer's jurisdiction."""

    items: List[ReviewQueueItemResponse] = Field(default_factory=list, description="Queue candidate items")
    total: int = Field(..., description="Total available items matching filter")


class SubmitDecisionRequest(BaseModel):
    """Payload for submitting a final review determination."""

    decision: OfficerDecision = Field(..., description="Final reviewer decision ('approve', 'reject', 'request_proof')")
    reason: str = Field(
        ...,
        min_length=10,
        max_length=5000,
        description="Mandatory factual basis explaining the decision rationale (10-5000 chars)",
    )


class CaseReviewResponse(BaseModel):
    """Verification review session details."""

    id: uuid.UUID = Field(..., description="Review record UUID")
    case_id: uuid.UUID = Field(..., description="Associated case UUID")
    reviewer_id: Optional[uuid.UUID] = Field(None, description="Reviewing officer UUID")
    reviewer_area_id: Optional[uuid.UUID] = Field(None, description="Officer area jurisdiction UUID")
    status: ReviewStatus = Field(..., description="Review execution status")
    started_at: Optional[datetime] = Field(None, description="Review commencement timestamp")
    completed_at: Optional[datetime] = Field(None, description="Review completion timestamp")
    decision: Optional[OfficerDecision] = Field(None, description="Submitted reviewer determination")
    decision_reason: Optional[str] = Field(None, description="Factual decision explanation")
    risk_score_at_decision: Optional[int] = Field(None, description="Snapshot risk score when decision was made")
    risk_level_at_decision: Optional[RiskLevel] = Field(None, description="Snapshot risk level when decision was made")
    created_at: datetime = Field(..., description="Record creation timestamp")
    updated_at: datetime = Field(..., description="Record modification timestamp")

    model_config = ConfigDict(from_attributes=True)


class StartReviewResponse(BaseModel):
    """Response when a reviewer acquires case review lock."""

    review: CaseReviewResponse = Field(..., description="Initialized review session")
    message: str = Field(..., description="Status summary")


class DecisionResponse(BaseModel):
    """Response returned upon successful review decision submission."""

    review: CaseReviewResponse = Field(..., description="Completed review record")
    case_status: CaseStatus = Field(..., description="Updated case lifecycle status")
    message: str = Field(..., description="Outcome notification message")


class ReviewHistoryResponse(BaseModel):
    """Immutable audit trail log record."""

    id: uuid.UUID = Field(..., description="Audit record UUID")
    case_id: uuid.UUID = Field(..., description="Case UUID")
    review_id: uuid.UUID = Field(..., description="Review session UUID")
    actor_id: uuid.UUID = Field(..., description="Acting officer user UUID")
    action: ReviewAction = Field(..., description="Audit action category")
    old_status: Optional[ReviewStatus] = Field(None, description="Previous review status")
    new_status: ReviewStatus = Field(..., description="Updated review status")
    old_decision: Optional[OfficerDecision] = Field(None, description="Previous decision")
    new_decision: Optional[OfficerDecision] = Field(None, description="Updated decision")
    reason: Optional[str] = Field(None, description="Associated rationale")
    created_at: datetime = Field(..., description="Timestamp of action")

    model_config = ConfigDict(from_attributes=True)


class ReviewDetailResponse(BaseModel):
    """Holistic case review package assembling all evidence, profiles, validations, and risk factors."""

    case: CaseResponse = Field(..., description="Case metadata")
    review: Optional[CaseReviewResponse] = Field(None, description="Current or completed review session")
    property_profile: Optional[PropertyProfileResponse] = Field(None, description="Consolidated property profile")
    documents: List[DocumentResponse] = Field(default_factory=list, description="Uploaded case documents")
    database_validation: Optional[ValidationRunDetailResponse] = Field(None, description="Government registry validation run")
    gis_validation: Optional[ValidationRunDetailResponse] = Field(None, description="GIS spatial validation run")
    mismatches: List[MismatchResponse] = Field(default_factory=list, description="Identified discrepancies with evidence links")
    risk_assessment: Optional[RiskAssessmentResponse] = Field(None, description="Deterministic risk assessment breakdown")
    history: List[ReviewHistoryResponse] = Field(default_factory=list, description="Audit trail history entries")
