from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
import uuid

from sqlalchemy import CheckConstraint, DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import RiskAssessmentStatus, RiskLevel

if TYPE_CHECKING:
    from app.models.case import Case
    from app.models.property_profile import PropertyProfile
    from app.models.risk_factor import RiskFactor
    from app.models.validation import ValidationRun


class RiskAssessment(Base):
    """Explainable, deterministic verification risk score and review priority classification for a case."""

    __tablename__ = "risk_assessments"

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
    property_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("property_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    property_profile_version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )
    risk_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    raw_score: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    risk_level: Mapped[RiskLevel] = mapped_column(
        SAEnum(
            RiskLevel,
            name="risk_level",
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        default=RiskLevel.LOW,
        nullable=False,
        index=True,
    )
    status: Mapped[RiskAssessmentStatus] = mapped_column(
        SAEnum(
            RiskAssessmentStatus,
            name="risk_assessment_status",
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        default=RiskAssessmentStatus.COMPLETED,
        nullable=False,
        index=True,
    )
    risk_version: Mapped[str] = mapped_column(
        String(20),
        default="1.0",
        nullable=False,
    )
    severity_rule_version: Mapped[str] = mapped_column(
        String(20),
        default="1.0",
        nullable=False,
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
    error_code: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    calculated_at: Mapped[datetime] = mapped_column(
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

    __table_args__ = (
        CheckConstraint("risk_score >= 0 AND risk_score <= 100", name="chk_risk_score_bounds"),
    )

    # Relationships
    case: Mapped["Case"] = relationship(
        "Case",
        back_populates="risk_assessments",
    )
    property_profile: Mapped["PropertyProfile"] = relationship(
        "PropertyProfile",
        back_populates="risk_assessments",
    )
    factors: Mapped[list["RiskFactor"]] = relationship(
        "RiskFactor",
        back_populates="risk_assessment",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="RiskFactor.points.desc()",
    )
