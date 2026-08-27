from datetime import datetime
from typing import Optional
import uuid
from pydantic import BaseModel, ConfigDict

from app.models.enums import CaseStatus, OfficerDecision, RiskLevel


class FinalDecisionResponse(BaseModel):
    """Detailed response schema for immutable case final determination snapshot."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    case_id: uuid.UUID
    review_id: uuid.UUID
    decided_by: uuid.UUID
    decision: OfficerDecision
    reason: str
    risk_assessment_id: Optional[uuid.UUID] = None
    risk_score_at_decision: Optional[int] = None
    risk_level_at_decision: Optional[RiskLevel] = None
    database_validation_run_id: Optional[uuid.UUID] = None
    gis_validation_run_id: Optional[uuid.UUID] = None
    property_profile_version: Optional[int] = None
    decided_at: datetime
    created_at: datetime


class CivilianCaseStatusResponse(BaseModel):
    """Simplified status view for civilian applicants."""

    model_config = ConfigDict(from_attributes=True)

    case_id: uuid.UUID
    status: CaseStatus
    updated_at: datetime
    title: Optional[str] = None
