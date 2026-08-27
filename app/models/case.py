from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
import uuid

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import CaseStatus, RiskLevel

if TYPE_CHECKING:
    from app.models.area import Area
    from app.models.audit_event import AuditEvent
    from app.models.final_decision import FinalDecision
    from app.models.mismatch import Mismatch
    from app.models.notification import Notification
    from app.models.proof_request import ProofRequest
    from app.models.property_profile import PropertyProfile
    from app.models.review import CaseReview
    from app.models.risk_assessment import RiskAssessment
    from app.models.user import User


class Case(Base):
    """Property Verification Case central entity."""

    __tablename__ = "cases"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    case_number: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    area_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("areas.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status: Mapped[CaseStatus] = mapped_column(
        SAEnum(
            CaseStatus,
            name="case_status",
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        default=CaseStatus.DRAFT,
        nullable=False,
        index=True,
    )
    risk_level: Mapped[RiskLevel] = mapped_column(
        SAEnum(
            RiskLevel,
            name="risk_level",
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        default=RiskLevel.UNKNOWN,
        nullable=False,
        index=True,
    )
    title: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    submitted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    reviewed_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    creator: Mapped["User"] = relationship(
        "User",
        foreign_keys=[created_by],
    )
    area: Mapped["Area"] = relationship(
        "Area",
        foreign_keys=[area_id],
    )
    reviewer: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[reviewed_by],
    )
    property_profile: Mapped[Optional["PropertyProfile"]] = relationship(
        "PropertyProfile",
        back_populates="case",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    mismatches: Mapped[list["Mismatch"]] = relationship(
        "Mismatch",
        back_populates="case",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Mismatch.created_at.desc()",
    )
    risk_assessments: Mapped[list["RiskAssessment"]] = relationship(
        "RiskAssessment",
        back_populates="case",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="RiskAssessment.created_at.desc()",
    )
    reviews: Mapped[list["CaseReview"]] = relationship(
        "CaseReview",
        back_populates="case",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="CaseReview.created_at.desc()",
    )
    proof_requests: Mapped[list["ProofRequest"]] = relationship(
        "ProofRequest",
        back_populates="case",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ProofRequest.created_at.desc()",
    )
    final_decision: Mapped[Optional["FinalDecision"]] = relationship(
        "FinalDecision",
        back_populates="case",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    audit_events: Mapped[list["AuditEvent"]] = relationship(
        "AuditEvent",
        back_populates="case",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="AuditEvent.created_at.asc()",
    )
    notifications: Mapped[list["Notification"]] = relationship(
        "Notification",
        back_populates="case",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Notification.created_at.desc()",
    )


class CaseSequence(Base):
    """Atomic year-scoped sequence counter for generating consecutive case numbers."""

    __tablename__ = "case_sequences"

    year: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )
    last_value: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
