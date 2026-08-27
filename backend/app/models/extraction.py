from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
import uuid

from sqlalchemy import DateTime, Enum as SAEnum, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import ExtractionStatus

if TYPE_CHECKING:
    from app.models.document import Document
    from app.models.evidence import Evidence
    from app.models.ocr_result import OCRResult


class ExtractedField(Base):
    """Candidate structured property attribute extracted from document OCR with confidence indicator."""

    __tablename__ = "extracted_fields"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ocr_result_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ocr_results.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    field_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    field_value: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    normalized_value: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    confidence: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    status: Mapped[ExtractionStatus] = mapped_column(
        SAEnum(
            ExtractionStatus,
            name="extraction_status",
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        default=ExtractionStatus.EXTRACTED,
        nullable=False,
        index=True,
    )
    extractor_version: Mapped[str] = mapped_column(
        String(20),
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
    document: Mapped["Document"] = relationship(
        "Document",
        back_populates="extracted_fields",
    )
    ocr_result: Mapped[Optional["OCRResult"]] = relationship(
        "OCRResult",
        foreign_keys=[ocr_result_id],
    )
    evidence_records: Mapped[list["Evidence"]] = relationship(
        "Evidence",
        back_populates="extracted_field",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
