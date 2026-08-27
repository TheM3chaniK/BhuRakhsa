from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
import uuid

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.property_profile import PropertyProfile


class PropertyFieldConflict(Base):
    """Record of conflicting values extracted across distinct pages/documents for the same property attribute."""

    __tablename__ = "property_field_conflicts"

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
    field_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    value_a: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    value_b: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    source_a: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    source_b: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    property_profile: Mapped["PropertyProfile"] = relationship(
        "PropertyProfile",
        back_populates="conflicts",
    )
