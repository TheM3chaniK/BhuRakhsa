from typing import List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import DocumentStatus


class OCRPageResponse(BaseModel):
    """Page-level OCR extracted text metadata."""

    page_number: int = Field(..., ge=1, description="1-indexed page number")
    text: str = Field(..., description="Raw text extracted by DeepSeek OCR")
    model_name: Optional[str] = Field(None, description="Ollama OCR model name used")
    processing_time_ms: Optional[int] = Field(None, ge=0, description="Processing duration in milliseconds")

    model_config = ConfigDict(from_attributes=True)


class DocumentOCRResponse(BaseModel):
    """Aggregated page-level OCR results for an entire document."""

    document_id: uuid.UUID = Field(..., description="Document UUID")
    status: DocumentStatus = Field(..., description="Current document status")
    pages: List[OCRPageResponse] = Field(default_factory=list, description="Extracted OCR text pages")

    model_config = ConfigDict(from_attributes=True)
