from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
import uuid

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import ValidationStatus, ValidationType

if TYPE_CHECKING:
    from app.models.property_profile import PropertyProfile
    from app.models.validation_candidate import ValidationCandidate
    from app.models.validation_result import ValidationResult


class ValidationRun(Base):
    """Execution session for external database or GIS cross-validation."""

    __tablename__ = "validation_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    property_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("property_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    validation_type: Mapped[ValidationType] = mapped_column(
        SAEnum(
            ValidationType,
            name="validation_type",
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
        index=True,
    )
    status: Mapped[ValidationStatus] = mapped_column(
        SAEnum(
            ValidationStatus,
            name="validation_status",
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        default=ValidationStatus.PENDING,
        nullable=False,
        index=True,
    )
    source_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    dataset_version: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    validator_version: Mapped[str] = mapped_column(
        String(20),
        default="1.0",
        nullable=False,
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
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
    property_profile: Mapped["PropertyProfile"] = relationship(
        "PropertyProfile",
        back_populates="validation_runs",
    )
    results: Mapped[list["ValidationResult"]] = relationship(
        "ValidationResult",
        back_populates="validation_run",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ValidationResult.created_at.asc()",
    )
    candidates: Mapped[list["ValidationCandidate"]] = relationship(
        "ValidationCandidate",
        back_populates="validation_run",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ValidationCandidate.match_score.desc()",
    )
