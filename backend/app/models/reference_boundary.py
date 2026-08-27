from datetime import datetime, timezone
from typing import Any, Optional
import uuid

from geoalchemy2 import Geometry
from sqlalchemy import DateTime, Enum as SAEnum, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import BoundaryType


class ReferenceBoundary(Base):
    """Authoritative administrative spatial jurisdiction boundary (District, Village, etc.)."""

    __tablename__ = "reference_boundaries"

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
    boundary_type: Mapped[BoundaryType] = mapped_column(
        SAEnum(
            BoundaryType,
            name="boundary_type",
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    normalized_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    # PostGIS geometry (SRID 4326 WGS84)
    geometry: Mapped[Any] = mapped_column(
        Geometry("MULTIPOLYGON", srid=4326, spatial_index=True),
        nullable=False,
    )

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
