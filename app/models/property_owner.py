from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
import uuid

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import OwnershipType

if TYPE_CHECKING:
    from app.models.property_profile import PropertyProfile


class PropertyOwner(Base):
    """Individual or entity owner associated with a canonical property profile."""

    __tablename__ = "property_owners"

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
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    normalized_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    ownership_type: Mapped[OwnershipType] = mapped_column(
        SAEnum(
            OwnershipType,
            name="ownership_type",
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        default=OwnershipType.UNKNOWN,
        nullable=False,
    )
    share: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    share_unit: Mapped[Optional[str]] = mapped_column(
        String(50),
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
        back_populates="owners",
    )
