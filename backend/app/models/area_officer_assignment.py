from datetime import datetime, timezone
from typing import TYPE_CHECKING
import uuid

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.area import Area
    from app.models.user import User


class AreaOfficerAssignment(Base):
    """Many-to-many assignment mapping between Area Officers and assigned Geographical Areas."""

    __tablename__ = "area_officer_assignments"
    __table_args__ = (
        UniqueConstraint("officer_id", "area_id", name="uq_officer_area"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    officer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    area_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("areas.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    officer: Mapped["User"] = relationship(
        "User",
        back_populates="officer_area_assignments",
    )
    area: Mapped["Area"] = relationship(
        "Area",
        back_populates="officer_assignments",
    )
