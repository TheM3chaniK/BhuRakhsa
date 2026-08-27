from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
import uuid

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.evidence import Evidence
    from app.models.extraction import ExtractedField
    from app.models.mismatch import Mismatch
    from app.models.validation_result import ValidationResult


class MismatchEvidence(Base):
    """Bidirectional traceability linkage connecting a discrepancy to underlying extraction and validation evidence."""

    __tablename__ = "mismatch_evidence"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    mismatch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("mismatches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    extracted_field_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("extracted_fields.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    validation_result_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("validation_results.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    evidence_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("evidence.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    mismatch: Mapped["Mismatch"] = relationship(
        "Mismatch",
        back_populates="evidence_links",
    )
    extracted_field: Mapped[Optional["ExtractedField"]] = relationship(
        "ExtractedField",
    )
    validation_result: Mapped[Optional["ValidationResult"]] = relationship(
        "ValidationResult",
    )
    evidence: Mapped[Optional["Evidence"]] = relationship(
        "Evidence",
    )
