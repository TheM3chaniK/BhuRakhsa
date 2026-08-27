from datetime import datetime
from typing import Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import DocumentStatus, ProcessingStatus


class ProcessDocumentResponse(BaseModel):
    """Response returned upon submitting a document for asynchronous OCR processing."""

    document_id: uuid.UUID = Field(..., description="Target document UUID")
    job_id: uuid.UUID = Field(..., description="Queued processing job UUID")
    document_status: DocumentStatus = Field(..., description="Current document status")
    processing_status: ProcessingStatus = Field(..., description="Current processing job status")

    model_config = ConfigDict(from_attributes=True)


class JobDetailResponse(BaseModel):
    """Detailed metadata for a document processing job."""

    job_id: uuid.UUID = Field(..., description="Processing job UUID")
    status: ProcessingStatus = Field(..., description="Job execution status")
    attempts: int = Field(..., ge=0, description="Number of execution attempts")
    started_at: Optional[datetime] = Field(None, description="Job execution start timestamp")
    completed_at: Optional[datetime] = Field(None, description="Job completion timestamp")
    error_code: Optional[str] = Field(None, description="Error category code if failed")
    error_message: Optional[str] = Field(None, description="Sanitized error description if failed")

    model_config = ConfigDict(from_attributes=True)


class DocumentProcessingStatusResponse(BaseModel):
    """Status inquiry response for a document's background processing pipeline."""

    document_id: uuid.UUID = Field(..., description="Document UUID")
    document_status: DocumentStatus = Field(..., description="Overall document status")
    processing: Optional[JobDetailResponse] = Field(None, description="Active or latest processing job details")

    model_config = ConfigDict(from_attributes=True)
