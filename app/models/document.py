from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
import uuid

from sqlalchemy import BigInteger, DateTime, Enum as SAEnum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import DocumentStatus

if TYPE_CHECKING:
    from app.models.case import Case
    from app.models.document_processing_job import DocumentProcessingJob
    from app.models.evidence import Evidence
    from app.models.extraction import ExtractedField
    from app.models.extraction_job import ExtractionJob
    from app.models.ocr_result import OCRResult
    from app.models.proof_request import ProofRequest
    from app.models.user import User


class Document(Base):
    """Uploaded property deed/evidence document metadata entity."""

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cases.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    proof_request_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("proof_requests.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    original_filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    stored_filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    mime_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    file_extension: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    file_size: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    sha256_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    storage_backend: Mapped[str] = mapped_column(
        String(50),
        default="local",
        nullable=False,
    )
    storage_key: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    status: Mapped[DocumentStatus] = mapped_column(
        SAEnum(
            DocumentStatus,
            name="document_status",
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        default=DocumentStatus.UPLOADED,
        nullable=False,
        index=True,
    )
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
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
    processed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    case: Mapped["Case"] = relationship(
        "Case",
        foreign_keys=[case_id],
    )
    proof_request: Mapped[Optional["ProofRequest"]] = relationship(
        "ProofRequest",
        back_populates="documents",
        foreign_keys=[proof_request_id],
    )
    uploader: Mapped["User"] = relationship(
        "User",
        foreign_keys=[uploaded_by],
    )
    processing_jobs: Mapped[list["DocumentProcessingJob"]] = relationship(
        "DocumentProcessingJob",
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="DocumentProcessingJob.created_at.desc()",
    )
    ocr_results: Mapped[list["OCRResult"]] = relationship(
        "OCRResult",
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="OCRResult.page_number.asc()",
    )
    extraction_jobs: Mapped[list["ExtractionJob"]] = relationship(
        "ExtractionJob",
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ExtractionJob.created_at.desc()",
    )
    extracted_fields: Mapped[list["ExtractedField"]] = relationship(
        "ExtractedField",
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ExtractedField.field_name.asc()",
    )
