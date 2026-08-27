from datetime import datetime, timezone
from typing import Any, TYPE_CHECKING, Optional
import uuid

from geoalchemy2 import Geometry
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.reference_property import ReferenceProperty


class ReferenceParcel(Base):
    """Authoritative cadastral reference parcel with spatial geometry."""

    __tablename__ = "reference_parcels"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    reference_property_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reference_properties.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
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

    # PostGIS geometries (SRID 4326 WGS84)
    geometry: Mapped[Any] = mapped_column(
        Geometry("MULTIPOLYGON", srid=4326, spatial_index=True),
        nullable=False,
    )
    centroid: Mapped[Optional[Any]] = mapped_column(
        Geometry("POINT", srid=4326, spatial_index=False),
        nullable=True,
    )

    # Area measurements
    area: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    area_unit: Mapped[Optional[str]] = mapped_column(
        String(50),
        default="sq_meters",
        nullable=True,
    )

    srid: Mapped[int] = mapped_column(Integer, default=4326, nullable=False)
    source_srid: Mapped[int] = mapped_column(Integer, default=4326, nullable=False)
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

    # Relationships
    reference_property: Mapped[Optional["ReferenceProperty"]] = relationship(
        "ReferenceProperty",
        back_populates="parcels",
    )
