from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
import uuid

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import ProofSubmissionStatus

if TYPE_CHECKING:
    from app.models.document import Document
    from app.models.proof_request import ProofRequest
    from app.models.user import User


class ProofSubmission(Base):
    """Evidentiary document upload submission answering a specific ProofRequest."""

    __tablename__ = "proof_submissions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    proof_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("proof_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    submitted_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[ProofSubmissionStatus] = mapped_column(
        SAEnum(
            ProofSubmissionStatus,
            name="proof_submission_status",
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        default=ProofSubmissionStatus.SUBMITTED,
        nullable=False,
        index=True,
    )
    comment: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
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
    proof_request: Mapped["ProofRequest"] = relationship(
        "ProofRequest",
        back_populates="submissions",
    )
    submitter: Mapped["User"] = relationship(
        "User",
        foreign_keys=[submitted_by],
    )
    document: Mapped["Document"] = relationship(
        "Document",
    )
