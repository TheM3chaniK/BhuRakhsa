from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
import uuid

from sqlalchemy import (
    DateTime,
    Float,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.reference_owner import ReferencePropertyOwner
    from app.models.reference_parcel import ReferenceParcel


class ReferenceProperty(Base):
    """Authoritative reference / government registry property record."""

    __tablename__ = "reference_properties"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    source_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    source_record_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    # Identifiers
    survey_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    plot_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    parcel_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    registration_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    deed_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)

    # Location & Jurisdiction
    property_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    district: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    subdivision: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    village: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    mouza: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    ward: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Physical Area
    property_area: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    area_unit: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    dataset_version: Mapped[str] = mapped_column(
        String(50),
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

    __table_args__ = (
        UniqueConstraint("source_id", "source_record_id", name="uq_reference_property_source"),
    )

    # Relationships
    owners: Mapped[list["ReferencePropertyOwner"]] = relationship(
        "ReferencePropertyOwner",
        back_populates="reference_property",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ReferencePropertyOwner.created_at.asc()",
    )
    parcels: Mapped[list["ReferenceParcel"]] = relationship(
        "ReferenceParcel",
        back_populates="reference_property",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
