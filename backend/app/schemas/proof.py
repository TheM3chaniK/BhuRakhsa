from datetime import datetime, timezone
from typing import List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.models.enums import (
    ProofRequestAction,
    ProofRequestStatus,
    ProofSubmissionStatus,
    ProofType,
)


class ProofRequestCreate(BaseModel):
    """Payload for creating a new supplementary evidentiary proof request."""

    title: str = Field(
        ...,
        min_length=3,
        max_length=200,
        description="Short and meaningful title of the request (3-200 chars)",
    )
    description: str = Field(
        ...,
        min_length=10,
        max_length=5000,
        description="Detailed explanation of required documentation (10-5000 chars)",
    )
    proof_type: ProofType = Field(
        default=ProofType.OWNERSHIP_DOCUMENT,
        description="Category of proof document requested",
    )
    due_at: Optional[datetime] = Field(
        None,
        description="Optional deadline timestamp for civilian submission",
    )
    review_id: Optional[uuid.UUID] = Field(
        None,
        description="Optional case review session identifier originating this request",
    )


class ProofRejectRequest(BaseModel):
    """Payload for rejecting a submitted proof request."""

    reason: str = Field(
        ...,
        min_length=10,
        max_length=5000,
        description="Mandatory explanation describing why the submitted proof was insufficient (10-5000 chars)",
    )


class ProofCancelRequest(BaseModel):
    """Payload for cancelling an open proof request."""

    reason: str = Field(
        ...,
        min_length=10,
        max_length=5000,
        description="Mandatory explanation describing why the proof request is being cancelled (10-5000 chars)",
    )


class ProofSubmissionResponse(BaseModel):
    """Record of a civilian proof upload submission."""

    id: uuid.UUID = Field(..., description="Submission UUID")
    proof_request_id: uuid.UUID = Field(..., description="Associated ProofRequest UUID")
    submitted_by: uuid.UUID = Field(..., description="Civilian submitter user UUID")
    document_id: uuid.UUID = Field(..., description="Uploaded case document UUID")
    status: ProofSubmissionStatus = Field(..., description="Submission processing status")
    comment: Optional[str] = Field(None, description="Civilian explanation or remarks")
    submitted_at: datetime = Field(..., description="Submission timestamp")
    created_at: datetime = Field(..., description="Record creation timestamp")

    model_config = ConfigDict(from_attributes=True)


class ProofRequestResponse(BaseModel):
    """Proof request detail with submissions."""

    id: uuid.UUID = Field(..., description="Proof request UUID")
    case_id: uuid.UUID = Field(..., description="Associated case UUID")
    review_id: Optional[uuid.UUID] = Field(None, description="Review session UUID")
    requested_by: uuid.UUID = Field(..., description="Requesting officer UUID")
    requested_from: uuid.UUID = Field(..., description="Civilian case owner UUID")
    proof_type: ProofType = Field(..., description="Requested document category")
    title: str = Field(..., description="Request title")
    description: str = Field(..., description="Request description instructions")
    status: ProofRequestStatus = Field(..., description="Current request status")
    due_at: Optional[datetime] = Field(None, description="Optional deadline timestamp")
    rejection_reason: Optional[str] = Field(None, description="Rejection reason if rejected")
    cancellation_reason: Optional[str] = Field(None, description="Cancellation reason if cancelled")
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp")
    created_at: datetime = Field(..., description="Request creation timestamp")
    updated_at: datetime = Field(..., description="Record modification timestamp")
    submissions: List[ProofSubmissionResponse] = Field(
        default_factory=list,
        description="List of civilian proof submissions for this request",
    )

    @computed_field
    @property
    def is_overdue(self) -> bool:
        """Dynamic check whether open request has passed its due_at deadline."""
        if self.due_at and self.status == ProofRequestStatus.OPEN:
            return datetime.now(timezone.utc) > self.due_at
        return False

    model_config = ConfigDict(from_attributes=True)


class ProofRequestHistoryResponse(BaseModel):
    """Immutable audit trail log record for proof request lifecycle."""

    id: uuid.UUID = Field(..., description="Audit record UUID")
    proof_request_id: uuid.UUID = Field(..., description="Associated ProofRequest UUID")
    actor_id: Optional[uuid.UUID] = Field(None, description="Acting user UUID if applicable")
    actor_type: str = Field(..., description="Actor category ('user' or 'system')")
    action: ProofRequestAction = Field(..., description="Audit action category")
    old_status: Optional[ProofRequestStatus] = Field(None, description="Previous request status")
    new_status: ProofRequestStatus = Field(..., description="Updated request status")
    reason: Optional[str] = Field(None, description="Associated rationale")
    created_at: datetime = Field(..., description="Timestamp of action")

    model_config = ConfigDict(from_attributes=True)
