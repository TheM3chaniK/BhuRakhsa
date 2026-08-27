from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
import uuid

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import MismatchSeverity

if TYPE_CHECKING:
    from app.models.mismatch import Mismatch
    from app.models.risk_assessment import RiskAssessment


class RiskFactor(Base):
    """Explainable risk factor contribution linking an identified discrepancy to awarded risk points."""

    __tablename__ = "risk_factors"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    risk_assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("risk_assessments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    mismatch_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("mismatches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    factor_code: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    severity: Mapped[MismatchSeverity] = mapped_column(
        SAEnum(
            MismatchSeverity,
            name="mismatch_severity",
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
    )
    points: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    risk_assessment: Mapped["RiskAssessment"] = relationship(
        "RiskAssessment",
        back_populates="factors",
    )
    mismatch: Mapped[Optional["Mismatch"]] = relationship(
        "Mismatch",
        back_populates="risk_factors",
    )
