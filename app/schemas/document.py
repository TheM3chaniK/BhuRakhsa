from datetime import datetime
from typing import List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import DocumentStatus


class DocumentResponse(BaseModel):
    """Document metadata schema (safe, without raw filesystem paths)."""

    id: uuid.UUID = Field(..., description="Unique document UUID")
    case_id: uuid.UUID = Field(..., description="Parent case UUID")
    original_filename: str = Field(..., description="Original uploaded filename")
    mime_type: str = Field(..., description="MIME content type")
    file_extension: str = Field(..., description="Normalized file extension")
    file_size: int = Field(..., ge=0, description="File size in bytes")
    sha256_hash: str = Field(..., description="SHA-256 binary hash")
    status: DocumentStatus = Field(..., description="Ingestion/OCR processing status")
    uploaded_by: uuid.UUID = Field(..., description="Uploader user UUID")
    created_at: datetime = Field(..., description="Upload timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    processed_at: Optional[datetime] = Field(None, description="OCR processing timestamp")

    model_config = ConfigDict(from_attributes=True)


class DocumentListResponse(BaseModel):
    """List of document metadata items for a case."""

    documents: List[DocumentResponse] = Field(..., description="List of case documents")
