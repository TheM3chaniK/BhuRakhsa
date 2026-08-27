from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
import uuid

from sqlalchemy import DateTime, Enum as SAEnum, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import MatchStatus

if TYPE_CHECKING:
    from app.models.validation import ValidationRun


class ValidationResult(Base):
    """Field-level outcome comparison between canonical document values and external reference registry records."""

    __tablename__ = "validation_results"

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
    field_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    document_value: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    reference_value: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    match_status: Mapped[MatchStatus] = mapped_column(
        SAEnum(
            MatchStatus,
            name="match_status",
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        default=MatchStatus.NOT_CHECKED,
        nullable=False,
    )
    match_score: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    mismatch_reason: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    source_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    source_record_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    # GIS / Spatial result extensions
    geometry_distance_meters: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    geometry_area: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    reference_area: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    coordinate_latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    coordinate_longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    validation_run: Mapped["ValidationRun"] = relationship(
        "ValidationRun",
        back_populates="results",
    )
