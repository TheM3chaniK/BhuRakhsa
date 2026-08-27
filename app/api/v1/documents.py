import urllib.parse
import uuid

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.enums import DocumentStatus, ProcessingStatus
from app.models.user import User
from app.schemas.auth import MessageResponse
from app.schemas.document import DocumentListResponse, DocumentResponse
from app.schemas.extraction import (
    DocumentEvidenceResponse,
    DocumentExtractionResponse,
    ExtractionJobResponse,
)
from app.schemas.ocr import DocumentOCRResponse, OCRPageResponse
from app.schemas.processing import (
    DocumentProcessingStatusResponse,
    JobDetailResponse,
    ProcessDocumentResponse,
)
from app.services.document_processing_service import DocumentProcessingService
from app.services.document_service import DocumentService
from app.services.extraction_service import ExtractionService
from app.workers.document_worker import DocumentWorker

router = APIRouter(tags=["Documents"])


@router.post(
    "/cases/{case_id}/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload Case Document",
    description="Upload a PDF, JPEG, or PNG document to a case (Civilian case owner only).",
)
async def upload_document(
    case_id: uuid.UUID,
    file: UploadFile = File(..., description="Document file (PDF, JPEG, PNG, max 25MB)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    """Upload and record a new case document."""
    document = await DocumentService.upload_document(
        db=db,
        case_id=case_id,
        user=current_user,
        upload_file=file,
    )
    return DocumentResponse.model_validate(document)


@router.get(
    "/cases/{case_id}/documents",
    response_model=DocumentListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Case Documents",
    description="Retrieve all active document metadata belonging to a case (requires case access).",
)
async def list_case_documents(
    case_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentListResponse:
    """List document metadata records for a case."""
    documents = await DocumentService.list_documents_for_case(
        db=db,
        case_id=case_id,
        user=current_user,
    )
    return DocumentListResponse(
        documents=[DocumentResponse.model_validate(doc) for doc in documents]
    )


@router.get(
    "/documents/{document_id}",
    response_model=DocumentResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Document Metadata",
    description="Retrieve metadata for a single document (requires case access).",
)
async def get_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    """Retrieve document metadata."""
    document = await DocumentService.get_document(
        db=db,
        document_id=document_id,
        user=current_user,
    )
    return DocumentResponse.model_validate(document)


@router.get(
    "/documents/{document_id}/download",
    status_code=status.HTTP_200_OK,
    summary="Download Document File",
    description="Stream the original document file content (requires case access).",
)
async def download_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Stream document content with appropriate content disposition headers."""
    doc, stream = await DocumentService.download_document(
        db=db,
        document_id=document_id,
        user=current_user,
    )

    safe_filename = urllib.parse.quote(doc.original_filename)

    headers = {
        "Content-Disposition": f'attachment; filename="{doc.original_filename}"; filename*=UTF-8\'\'{safe_filename}',
        "Content-Length": str(doc.file_size),
    }

    return StreamingResponse(
        stream,
        media_type=doc.mime_type,
        headers=headers,
    )


@router.delete(
    "/documents/{document_id}",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete Case Document",
    description="Soft delete a document (Civilian owner only, while case is in DRAFT status).",
)
async def delete_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Soft delete a document."""
    await DocumentService.delete_document(
        db=db,
        document_id=document_id,
        user=current_user,
    )
    return MessageResponse(message="Document deleted successfully.")


# =============================================================================
# Step 8: Asynchronous Document Processing & DeepSeek OCR Endpoints
# =============================================================================


@router.post(
    "/documents/{document_id}/process",
    response_model=ProcessDocumentResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Enqueue Document for OCR Processing",
    description="Queue document for asynchronous DeepSeek OCR preprocessing via Ollama (requires case access).",
)
async def process_document(
    document_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProcessDocumentResponse:
    """Enqueue document for asynchronous OCR processing."""
    doc, job = await DocumentProcessingService.queue_document_processing(
        db=db,
        document_id=document_id,
        user=current_user,
    )

    if job.status == ProcessingStatus.QUEUED:
        background_tasks.add_task(DocumentWorker._execute_job, job.id)

    return ProcessDocumentResponse(
        document_id=doc.id,
        job_id=job.id,
        document_status=doc.status,
        processing_status=job.status,
    )


@router.get(
    "/documents/{document_id}/processing",
    response_model=DocumentProcessingStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Document Processing Status",
    description="Check the execution status of asynchronous OCR processing jobs for a document.",
)
async def get_document_processing_status(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentProcessingStatusResponse:
    """Get document processing status and job details."""
    doc, job = await DocumentProcessingService.get_processing_status(
        db=db,
        document_id=document_id,
        user=current_user,
    )
    job_detail = (
        JobDetailResponse(
            job_id=job.id,
            status=job.status,
            attempts=job.attempts,
            started_at=job.started_at,
            completed_at=job.completed_at,
            error_code=job.error_code,
            error_message=job.error_message,
        )
        if job
        else None
    )
    return DocumentProcessingStatusResponse(
        document_id=doc.id,
        document_status=doc.status,
        processing=job_detail,
    )


@router.get(
    "/documents/{document_id}/ocr",
    response_model=DocumentOCRResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Extracted OCR Text",
    description="Retrieve page-level text extracted by DeepSeek OCR (requires case access).",
)
async def get_document_ocr_results(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentOCRResponse:
    """Retrieve extracted page-level OCR results."""
    doc, ocr_results = await DocumentProcessingService.get_ocr_results(
        db=db,
        document_id=document_id,
        user=current_user,
    )
    pages = [
        OCRPageResponse(
            page_number=res.page_number,
            text=res.text,
            model_name=res.model_name,
            processing_time_ms=res.processing_time_ms,
        )
        for res in ocr_results
    ]
    return DocumentOCRResponse(
        document_id=doc.id,
        status=doc.status,
        pages=pages,
    )


# =============================================================================
# Step 9: Structured Field Extraction & Evidence Endpoints
# =============================================================================


@router.post(
    "/documents/{document_id}/extract",
    response_model=ExtractionJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Enqueue Document for Structured Field Extraction",
    description="Queue document for asynchronous LLM structured field extraction and evidence grounding (requires completed OCR).",
)
async def extract_document_fields(
    document_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExtractionJobResponse:
    """Enqueue document for structured field extraction."""
    doc, job = await ExtractionService.queue_extraction(
        db=db,
        document_id=document_id,
        user=current_user,
    )

    if job.status == ProcessingStatus.QUEUED:
        background_tasks.add_task(DocumentWorker._execute_extraction_job, job.id)

    return ExtractionJobResponse(
        document_id=doc.id,
        job_id=job.id,
        status=job.status,
    )


@router.get(
    "/documents/{document_id}/extraction",
    response_model=DocumentExtractionResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Document Structured Extraction Results",
    description="Retrieve all candidate structured property fields extracted from document OCR.",
)
async def get_document_extraction(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentExtractionResponse:
    """Retrieve structured candidate fields extracted for a document."""
    return await ExtractionService.get_extraction_results(
        db=db,
        document_id=document_id,
        user=current_user,
    )


@router.get(
    "/documents/{document_id}/evidence",
    response_model=DocumentEvidenceResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Document Extraction Evidence Links",
    description="Retrieve extracted fields grouped with supporting page citations and grounded source OCR text.",
)
async def get_document_evidence(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentEvidenceResponse:
    """Retrieve grounded evidence citations for all extracted fields."""
    return await ExtractionService.get_document_evidence(
        db=db,
        document_id=document_id,
        user=current_user,
    )
