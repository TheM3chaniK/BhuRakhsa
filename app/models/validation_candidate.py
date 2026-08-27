from datetime import datetime, timezone
from typing import TYPE_CHECKING
import uuid

from sqlalchemy import DateTime, Enum as SAEnum, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import CandidateSelectionStatus

if TYPE_CHECKING:
    from app.models.validation import ValidationRun


class ValidationCandidate(Base):
    """Candidate reference property matched and ranked during validation candidate search."""

    __tablename__ = "validation_candidates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    validation_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("validation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    source_record_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    match_score: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    selection_status: Mapped[CandidateSelectionStatus] = mapped_column(
        SAEnum(
            CandidateSelectionStatus,
            name="candidate_selection_status",
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        default=CandidateSelectionStatus.CANDIDATE,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    validation_run: Mapped["ValidationRun"] = relationship(
        "ValidationRun",
        back_populates="candidates",
    )
