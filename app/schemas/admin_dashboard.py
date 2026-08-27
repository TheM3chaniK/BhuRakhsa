from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import CaseStatus, RiskLevel
from app.schemas.audit import AuditEventResponse
from app.schemas.case import CaseResponse
from app.schemas.document import DocumentResponse
from app.schemas.extraction import ExtractedFieldResponse
from app.schemas.final_decision import FinalDecisionResponse
from app.schemas.ocr import OCRPageResponse
from app.schemas.proof import ProofRequestResponse
from app.schemas.property_profile import PropertyProfileResponse
from app.schemas.review import CaseReviewResponse
from app.schemas.risk import MismatchResponse, RiskAssessmentResponse
from app.schemas.validation import ValidationRunDetailResponse


# =============================================================================
# Dashboard Schemas
# =============================================================================


class AreaSummaryCounts(BaseModel):
    """Area count breakdown."""
    total: int = Field(..., ge=0)
    active: int = Field(..., ge=0)


class UserSummaryCounts(BaseModel):
    """User account count breakdown."""
    civilians: int = Field(..., ge=0)
    area_officers: int = Field(..., ge=0)


class CaseSummaryCounts(BaseModel):
    """Case lifecycle count breakdown."""
    total: int = Field(..., ge=0)
    under_review: int = Field(..., ge=0)
    proof_required: int = Field(..., ge=0)
    approved: int = Field(..., ge=0)
    rejected: int = Field(..., ge=0)


class RiskSummaryCounts(BaseModel):
    """Risk tier count breakdown."""
    critical: int = Field(..., ge=0)
    high: int = Field(..., ge=0)
    medium: int = Field(..., ge=0)
    low: int = Field(..., ge=0)


class ProcessingSummaryCounts(BaseModel):
    """Document and validation processing job counts."""
    ocr_pending: int = Field(..., ge=0)
    ocr_failed: int = Field(..., ge=0)
    validation_pending: int = Field(..., ge=0)
    validation_failed: int = Field(..., ge=0)


class AdminDashboardResponse(BaseModel):
    """Consolidated Super Admin Dashboard metrics."""
    areas: AreaSummaryCounts
    users: UserSummaryCounts
    cases: CaseSummaryCounts
    risk: RiskSummaryCounts
    processing: ProcessingSummaryCounts


class OfficerDashboardResponse(BaseModel):
    """Scoped Area Officer Dashboard metrics."""
    assigned_areas: List[uuid.UUID]
    cases: CaseSummaryCounts
    risk: RiskSummaryCounts
    queue: Dict[str, int]


# =============================================================================
# Statistics Schemas
# =============================================================================


class CaseStatisticsResponse(BaseModel):
    """Aggregated case statistics."""
    total_cases: int
    by_status: Dict[str, int]
    by_area: Dict[str, int]


class RiskStatisticsResponse(BaseModel):
    """Aggregated risk assessment statistics."""
    total_assessed: int
    by_risk_level: Dict[str, int]
    average_risk_score: float


class ReviewStatisticsResponse(BaseModel):
    """Aggregated review and officer determination metrics."""
    total_reviews: int
    by_decision: Dict[str, int]
    by_status: Dict[str, int]


class ProofStatisticsResponse(BaseModel):
    """Aggregated supplementary proof metrics."""
    total_requests: int
    by_status: Dict[str, int]
    by_proof_type: Dict[str, int]


class ProcessingStatisticsResponse(BaseModel):
    """Aggregated background processing metrics."""
    total_jobs: int
    by_status: Dict[str, int]
    success_rate_percentage: float


class OfficerStatisticsResponse(BaseModel):
    """Aggregated officer performance and workload statistics."""
    total_officers: int
    assigned_officers: int
    unassigned_officers: int
    reviews_per_officer: Dict[str, int]


# =============================================================================
# Queue & Failed Job Monitoring Schemas
# =============================================================================


class QueueSummaryItem(BaseModel):
    """Status counts for a single background queue."""
    pending: int = Field(default=0, ge=0)
    processing: int = Field(default=0, ge=0)
    failed: int = Field(default=0, ge=0)


class QueueMonitoringResponse(BaseModel):
    """System-wide background processing queue depths."""
    ocr: QueueSummaryItem
    extraction: QueueSummaryItem
    validation: QueueSummaryItem
    gis: QueueSummaryItem
    revalidation: QueueSummaryItem
    outbox: QueueSummaryItem


class FailedJobResponse(BaseModel):
    """Failed background task representation."""
    job_id: uuid.UUID
    job_type: str
    case_id: Optional[uuid.UUID] = None
    status: str
    attempt_count: int
    created_at: datetime
    updated_at: datetime
    error_message: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class FailedJobListResponse(BaseModel):
    """Paginated list of failed background jobs."""
    items: List[FailedJobResponse]
    total: int
    page: int
    page_size: int


class JobRetryResponse(BaseModel):
    """Outcome confirmation of manual job retry."""
    job_id: uuid.UUID
    success: bool
    message: str


# =============================================================================
# Detailed System Health Schemas
# =============================================================================


class SystemComponentHealth(BaseModel):
    """Operational status of an individual system component."""
    status: str = Field(..., description="'healthy', 'degraded', or 'unhealthy'")
    details: Optional[Dict[str, Any]] = None


class AdminSystemHealthResponse(BaseModel):
    """Detailed multi-component system health report (Super Admin only)."""
    status: str = Field(..., description="Overall system status ('healthy', 'degraded', 'unhealthy')")
    components: Dict[str, SystemComponentHealth]
    timestamp: datetime


# =============================================================================
# Admin Case 360-Degree Operational Detail Schema
# =============================================================================


class AdminCaseDetailResponse(BaseModel):
    """Comprehensive operational view of a case across all intelligence layers."""
    case: CaseResponse
    property_profile: Optional[PropertyProfileResponse] = None
    documents: List[DocumentResponse] = Field(default_factory=list)
    ocr_pages: List[OCRPageResponse] = Field(default_factory=list)
    extracted_fields: List[ExtractedFieldResponse] = Field(default_factory=list)
    database_validation_runs: List[ValidationRunDetailResponse] = Field(default_factory=list)
    gis_validation_runs: List[ValidationRunDetailResponse] = Field(default_factory=list)
    mismatches: List[MismatchResponse] = Field(default_factory=list)
    risk_assessments: List[RiskAssessmentResponse] = Field(default_factory=list)
    reviews: List[CaseReviewResponse] = Field(default_factory=list)
    proof_requests: List[ProofRequestResponse] = Field(default_factory=list)
    final_decision: Optional[FinalDecisionResponse] = None
    audit_events: List[AuditEventResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
