from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
import uuid

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import MismatchSeverity, MismatchSource, MismatchType

if TYPE_CHECKING:
    from app.models.case import Case
    from app.models.mismatch_evidence import MismatchEvidence
    from app.models.property_profile import PropertyProfile
    from app.models.risk_factor import RiskFactor
    from app.models.validation import ValidationRun


class Mismatch(Base):
    """Normalized discrepancy identified between document, extraction, reference registry, or GIS layers."""

    __tablename__ = "mismatches"

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
    validation_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("validation_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    mismatch_type: Mapped[MismatchType] = mapped_column(
        SAEnum(
            MismatchType,
            name="mismatch_type",
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
        index=True,
    )
    mismatch_source: Mapped[MismatchSource] = mapped_column(
        SAEnum(
            MismatchSource,
            name="mismatch_source",
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
        index=True,
    )
    field_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    document_value: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    reference_value: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    severity: Mapped[MismatchSeverity] = mapped_column(
        SAEnum(
            MismatchSeverity,
            name="mismatch_severity",
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
        index=True,
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    rule_version: Mapped[str] = mapped_column(
        String(20),
        default="1.0",
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
    case: Mapped["Case"] = relationship(
        "Case",
        back_populates="mismatches",
    )
    property_profile: Mapped["PropertyProfile"] = relationship(
        "PropertyProfile",
        back_populates="mismatches",
    )
    validation_run: Mapped[Optional["ValidationRun"]] = relationship(
        "ValidationRun",
    )
    evidence_links: Mapped[list["MismatchEvidence"]] = relationship(
        "MismatchEvidence",
        back_populates="mismatch",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    risk_factors: Mapped[list["RiskFactor"]] = relationship(
        "RiskFactor",
        back_populates="mismatch",
    )
