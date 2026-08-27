from datetime import datetime, timezone
from typing import Any, Dict, Optional
import uuid
from pydantic import BaseModel, Field


class DomainEvent(BaseModel):
    """Base domain event envelope."""

    event_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CaseApprovedEvent(DomainEvent):
    """Event emitted when a property case is approved."""

    case_id: uuid.UUID
    review_id: uuid.UUID
    decided_by: uuid.UUID
    owner_id: uuid.UUID
    reason: str
    risk_score: Optional[int] = None
    risk_level: Optional[str] = None


class CaseRejectedEvent(DomainEvent):
    """Event emitted when a property case is rejected."""

    case_id: uuid.UUID
    review_id: uuid.UUID
    decided_by: uuid.UUID
    owner_id: uuid.UUID
    reason: str
    risk_score: Optional[int] = None
    risk_level: Optional[str] = None


class ProofRequestedEvent(DomainEvent):
    """Event emitted when an officer requests additional proof."""

    proof_request_id: uuid.UUID
    case_id: uuid.UUID
    requested_by: uuid.UUID
    requested_from: uuid.UUID
    title: str
    description: str
    proof_type: str


class ProofSubmittedEvent(DomainEvent):
    """Event emitted when a civilian submits requested proof."""

    proof_request_id: uuid.UUID
    case_id: uuid.UUID
    area_id: uuid.UUID
    submitted_by: uuid.UUID
    document_id: uuid.UUID


class ProofAcceptedEvent(DomainEvent):
    """Event emitted when an officer accepts a proof request."""

    proof_request_id: uuid.UUID
    case_id: uuid.UUID
    accepted_by: uuid.UUID
    requested_from: uuid.UUID


class ProofRejectedEvent(DomainEvent):
    """Event emitted when an officer rejects a proof request."""

    proof_request_id: uuid.UUID
    case_id: uuid.UUID
    rejected_by: uuid.UUID
    requested_from: uuid.UUID
    reason: str


class CaseCreatedEvent(DomainEvent):
    """Event emitted when a new case is created."""

    case_id: uuid.UUID
    created_by: uuid.UUID
    area_id: uuid.UUID
