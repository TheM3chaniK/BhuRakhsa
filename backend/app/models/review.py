from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
import uuid

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import OfficerDecision, ReviewStatus, RiskLevel

if TYPE_CHECKING:
    from app.models.area import Area
    from app.models.case import Case
    from app.models.review_history import ReviewHistory
    from app.models.risk_assessment import RiskAssessment
    from app.models.user import User
    from app.models.validation import ValidationRun


class CaseReview(Base):
    """Area Officer verification review session and final decision record for a case."""

    __tablename__ = "case_reviews"

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
    reviewer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    reviewer_area_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("areas.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[ReviewStatus] = mapped_column(
        SAEnum(
            ReviewStatus,
            name="review_status",
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        default=ReviewStatus.NOT_STARTED,
        nullable=False,
        index=True,
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    decision: Mapped[Optional[OfficerDecision]] = mapped_column(
        SAEnum(
            OfficerDecision,
            name="officer_decision",
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=True,
        index=True,
    )
    decision_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Auditable snapshots at decision time
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
    risk_assessment_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("risk_assessments.id", ondelete="SET NULL"),
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
        back_populates="reviews",
    )
    reviewer: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[reviewer_id],
    )
    reviewer_area: Mapped[Optional["Area"]] = relationship(
        "Area",
        foreign_keys=[reviewer_area_id],
    )
    risk_assessment: Mapped[Optional["RiskAssessment"]] = relationship(
        "RiskAssessment",
        foreign_keys=[risk_assessment_id],
    )
    history_entries: Mapped[list["ReviewHistory"]] = relationship(
        "ReviewHistory",
        back_populates="review",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ReviewHistory.created_at.asc()",
    )
