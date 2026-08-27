from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
import uuid

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import ProofRequestStatus, ProofType

if TYPE_CHECKING:
    from app.models.case import Case
    from app.models.document import Document
    from app.models.proof_request_history import ProofRequestHistory
    from app.models.proof_submission import ProofSubmission
    from app.models.review import CaseReview
    from app.models.user import User


class ProofRequest(Base):
    """Formal request issued by an Area Officer to a Civilian for supplementary evidentiary documentation."""

    __tablename__ = "proof_requests"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    review_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("case_reviews.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    requested_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    requested_from: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    proof_type: Mapped[ProofType] = mapped_column(
        SAEnum(
            ProofType,
            name="proof_type",
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        default=ProofType.OWNERSHIP_DOCUMENT,
        nullable=False,
    )
    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    status: Mapped[ProofRequestStatus] = mapped_column(
        SAEnum(
            ProofRequestStatus,
            name="proof_request_status",
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        default=ProofRequestStatus.OPEN,
        nullable=False,
        index=True,
    )
    due_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    rejection_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    cancellation_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    case: Mapped["Case"] = relationship(
        "Case",
        back_populates="proof_requests",
    )
    review: Mapped[Optional["CaseReview"]] = relationship(
        "CaseReview",
    )
    requester: Mapped["User"] = relationship(
        "User",
        foreign_keys=[requested_by],
    )
    civilian: Mapped["User"] = relationship(
        "User",
        foreign_keys=[requested_from],
    )
    submissions: Mapped[list["ProofSubmission"]] = relationship(
        "ProofSubmission",
        back_populates="proof_request",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ProofSubmission.submitted_at.desc()",
    )
    documents: Mapped[list["Document"]] = relationship(
        "Document",
        back_populates="proof_request",
    )
    history_entries: Mapped[list["ProofRequestHistory"]] = relationship(
        "ProofRequestHistory",
        back_populates="proof_request",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ProofRequestHistory.created_at.asc()",
    )
