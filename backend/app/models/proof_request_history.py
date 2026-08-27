from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
import uuid

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import ProofRequestAction, ProofRequestStatus

if TYPE_CHECKING:
    from app.models.proof_request import ProofRequest
    from app.models.user import User


class ProofRequestHistory(Base):
    """Immutable audit trail log for proof request lifecycle transitions and officer/civilian actions."""

    __tablename__ = "proof_request_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    proof_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("proof_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    actor_type: Mapped[str] = mapped_column(
        String(20),
        default="user",
        nullable=False,
    )
    action: Mapped[ProofRequestAction] = mapped_column(
        SAEnum(
            ProofRequestAction,
            name="proof_request_action",
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
    )
    old_status: Mapped[Optional[ProofRequestStatus]] = mapped_column(
        SAEnum(
            ProofRequestStatus,
            name="proof_request_status",
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=True,
    )
    new_status: Mapped[ProofRequestStatus] = mapped_column(
        SAEnum(
            ProofRequestStatus,
            name="proof_request_status",
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
    )
    reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    # Relationships
    proof_request: Mapped["ProofRequest"] = relationship(
        "ProofRequest",
        back_populates="history_entries",
    )
    actor: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[actor_id],
    )
