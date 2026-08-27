from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
import uuid

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import OfficerDecision, ReviewAction, ReviewStatus

if TYPE_CHECKING:
    from app.models.case import Case
    from app.models.review import CaseReview
    from app.models.user import User


class ReviewHistory(Base):
    """Immutable audit trail log for review actions, state transitions, and officer decisions."""

    __tablename__ = "review_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    review_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("case_reviews.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    action: Mapped[ReviewAction] = mapped_column(
        SAEnum(
            ReviewAction,
            name="review_action",
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
    )
    old_status: Mapped[Optional[ReviewStatus]] = mapped_column(
        SAEnum(
            ReviewStatus,
            name="review_status",
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=True,
    )
    new_status: Mapped[ReviewStatus] = mapped_column(
        SAEnum(
            ReviewStatus,
            name="review_status",
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
    )
    old_decision: Mapped[Optional[OfficerDecision]] = mapped_column(
        SAEnum(
            OfficerDecision,
            name="officer_decision",
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=True,
    )
    new_decision: Mapped[Optional[OfficerDecision]] = mapped_column(
        SAEnum(
            OfficerDecision,
            name="officer_decision",
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=True,
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
    case: Mapped["Case"] = relationship(
        "Case",
    )
    review: Mapped["CaseReview"] = relationship(
        "CaseReview",
        back_populates="history_entries",
    )
    actor: Mapped["User"] = relationship(
        "User",
        foreign_keys=[actor_id],
    )
