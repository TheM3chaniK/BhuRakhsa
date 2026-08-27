from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional
import uuid

from geoalchemy2 import Geometry
from sqlalchemy import (
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import CoordinateSource, ProfileStatus

if TYPE_CHECKING:
    from app.models.case import Case
    from app.models.mismatch import Mismatch
    from app.models.property_field_conflict import PropertyFieldConflict
    from app.models.property_field_source import PropertyFieldSource
    from app.models.property_owner import PropertyOwner
    from app.models.risk_assessment import RiskAssessment
    from app.models.validation import ValidationRun


class PropertyProfile(Base):
    """Canonical Evidence-linked Property Profile consolidated from extracted document fields."""

    __tablename__ = "property_profiles"

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
    status: Mapped[ProfileStatus] = mapped_column(
        SAEnum(
            ProfileStatus,
            name="profile_status",
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        default=ProfileStatus.DRAFT,
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )

    # Identifiers
    property_identifier: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    survey_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    plot_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    parcel_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    registration_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    deed_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Location & Jurisdiction
    property_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    district: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    subdivision: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    village: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    mouza: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    ward: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Area
    property_area: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    area_unit: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Coordinates
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # PostGIS spatial features (SRID 4326 WGS84)
    location_point: Mapped[Optional[Any]] = mapped_column(
        Geometry("POINT", srid=4326, spatial_index=True),
        nullable=True,
    )
    coordinate_source: Mapped[Optional[CoordinateSource]] = mapped_column(
        SAEnum(
            CoordinateSource,
            name="coordinate_source",
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=True,
    )
    parcel_geometry: Mapped[Optional[Any]] = mapped_column(
        Geometry("MULTIPOLYGON", srid=4326, spatial_index=True),
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
        back_populates="property_profile",
    )
    owners: Mapped[list["PropertyOwner"]] = relationship(
        "PropertyOwner",
        back_populates="property_profile",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="PropertyOwner.created_at.asc()",
    )
    field_sources: Mapped[list["PropertyFieldSource"]] = relationship(
        "PropertyFieldSource",
        back_populates="property_profile",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    conflicts: Mapped[list["PropertyFieldConflict"]] = relationship(
        "PropertyFieldConflict",
        back_populates="property_profile",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    validation_runs: Mapped[list["ValidationRun"]] = relationship(
        "ValidationRun",
        back_populates="property_profile",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ValidationRun.created_at.desc()",
    )
    mismatches: Mapped[list["Mismatch"]] = relationship(
        "Mismatch",
        back_populates="property_profile",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Mismatch.created_at.desc()",
    )
    risk_assessments: Mapped[list["RiskAssessment"]] = relationship(
        "RiskAssessment",
        back_populates="property_profile",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="RiskAssessment.created_at.desc()",
    )
