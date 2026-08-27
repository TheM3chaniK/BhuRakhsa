from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
import uuid

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import OfficerDecision, RiskLevel

if TYPE_CHECKING:
    from app.models.case import Case
    from app.models.review import CaseReview
    from app.models.risk_assessment import RiskAssessment
    from app.models.user import User
    from app.models.validation import ValidationRun


class FinalDecision(Base):
    """Immutable terminal decision record for a property verification case."""

    __tablename__ = "final_decisions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cases.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    review_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("case_reviews.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    decided_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    decision: Mapped[OfficerDecision] = mapped_column(
        SAEnum(
            OfficerDecision,
            name="officer_decision",
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
    )
    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # Auditable snapshots at decision time
    risk_assessment_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("risk_assessments.id", ondelete="SET NULL"),
        nullable=True,
    )
    risk_score_at_decision: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    risk_level_at_decision: Mapped[Optional[RiskLevel]] = mapped_column(
        SAEnum(
            RiskLevel,
            name="risk_level",
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=True,
    )
    database_validation_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("validation_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    gis_validation_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("validation_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    property_profile_version: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    case: Mapped["Case"] = relationship(
        "Case",
        back_populates="final_decision",
    )
    review: Mapped["CaseReview"] = relationship(
        "CaseReview",
    )
    decider: Mapped["User"] = relationship(
        "User",
        foreign_keys=[decided_by],
    )
    risk_assessment: Mapped[Optional["RiskAssessment"]] = relationship(
        "RiskAssessment",
        foreign_keys=[risk_assessment_id],
    )
