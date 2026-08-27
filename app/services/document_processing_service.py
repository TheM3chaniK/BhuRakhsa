from datetime import datetime, timezone
import hashlib
from pathlib import Path
import tempfile
from typing import Optional, Sequence, Tuple
import uuid

import anyio
from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import logger
from app.db.session import async_session_factory
from app.models.case import Case
from app.models.document import Document
from app.models.document_processing_job import DocumentProcessingJob
from app.models.enums import DocumentStatus, ProcessingStatus
from app.models.ocr_result import OCRResult
from app.models.user import User
from app.services.case_access_service import CaseAccessService
from app.services.ocr_service import OcrService
from app.services.ollama_service import OllamaService, OllamaServiceException
from app.storage import get_storage_backend


class DocumentProcessingService:
    """Service orchestrating asynchronous document OCR processing, job tracking, and result persistence."""

    @staticmethod
    async def queue_document_processing(
        db: AsyncSession, document_id: uuid.UUID, user: User
    ) -> Tuple[Document, DocumentProcessingJob]:
        """Validate document access and enqueue an asynchronous OCR processing job."""
        # 1. Fetch document
        doc_res = await db.execute(
            select(Document).where(
                Document.id == document_id, Document.deleted_at.is_(None)
            )
        )
        document = doc_res.scalar_one_or_none()
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found.",
            )

        # 2. Fetch case and verify access
        case_res = await db.execute(select(Case).where(Case.id == document.case_id))
        case = case_res.scalar_one_or_none()
        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Associated case not found.",
            )
        await CaseAccessService.verify_case_access(db, user, case)

        # 3. Check for existing active or completed processing
        active_job_res = await db.execute(
            select(DocumentProcessingJob)
            .where(
                DocumentProcessingJob.document_id == document.id,
                DocumentProcessingJob.status.in_(
                    [ProcessingStatus.QUEUED, ProcessingStatus.PROCESSING]
                ),
            )
            .order_by(DocumentProcessingJob.created_at.desc())
        )
        active_job = active_job_res.scalars().first()
        if active_job:
            # Idempotently return the existing active job
            return document, active_job

        if document.status == DocumentStatus.PROCESSED:
            # Document is already processed
            latest_job_res = await db.execute(
                select(DocumentProcessingJob)
                .where(DocumentProcessingJob.document_id == document.id)
                .order_by(DocumentProcessingJob.created_at.desc())
            )
            latest_job = latest_job_res.scalars().first()
            if latest_job:
                return document, latest_job

        # 4. Create new processing job
        job = DocumentProcessingJob(
            id=uuid.uuid4(),
            document_id=document.id,
            status=ProcessingStatus.QUEUED,
            attempts=0,
        )
        document.status = DocumentStatus.QUEUED
        db.add(job)
        await db.commit()
        await db.refresh(job)
        await db.refresh(document)

        return document, job

    @staticmethod
    async def queue_processing_job(
        db: AsyncSession, document_id: uuid.UUID
    ) -> DocumentProcessingJob:
        """Enqueue an asynchronous OCR processing job directly for a document."""
        job = DocumentProcessingJob(
            id=uuid.uuid4(),
            document_id=document_id,
            status=ProcessingStatus.QUEUED,
            attempts=0,
        )
        db.add(job)
        await db.flush()
        return job

    @staticmethod
    async def get_processing_status(
        db: AsyncSession, document_id: uuid.UUID, user: User
    ) -> Tuple[Document, Optional[DocumentProcessingJob]]:
        """Retrieve overall document status and latest processing job details."""
        doc_res = await db.execute(
            select(Document).where(
                Document.id == document_id, Document.deleted_at.is_(None)
            )
        )
        document = doc_res.scalar_one_or_none()
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found.",
            )

        case_res = await db.execute(select(Case).where(Case.id == document.case_id))
        case = case_res.scalar_one_or_none()
        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Associated case not found.",
            )
        await CaseAccessService.verify_case_access(db, user, case)

        job_res = await db.execute(
            select(DocumentProcessingJob)
            .where(DocumentProcessingJob.document_id == document.id)
            .order_by(DocumentProcessingJob.created_at.desc())
        )
        latest_job = job_res.scalars().first()
        return document, latest_job

    @staticmethod
    async def get_ocr_results(
        db: AsyncSession, document_id: uuid.UUID, user: User
    ) -> Tuple[Document, Sequence[OCRResult]]:
        """Retrieve all page-level OCR results extracted from the document."""
        doc_res = await db.execute(
            select(Document).where(
                Document.id == document_id, Document.deleted_at.is_(None)
            )
        )
        document = doc_res.scalar_one_or_none()
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found.",
            )

        case_res = await db.execute(select(Case).where(Case.id == document.case_id))
        case = case_res.scalar_one_or_none()
        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Associated case not found.",
            )
        await CaseAccessService.verify_case_access(db, user, case)

        results_res = await db.execute(
            select(OCRResult)
            .where(OCRResult.document_id == document.id)
            .order_by(OCRResult.page_number.asc())
        )
        return document, results_res.scalars().all()

    @staticmethod
    async def execute_processing_job(job_id: uuid.UUID) -> None:
        """Background worker execution pipeline for DeepSeek OCR via Ollama."""
        async with async_session_factory() as db:
            job_res = await db.execute(
                select(DocumentProcessingJob).where(DocumentProcessingJob.id == job_id)
            )
            job = job_res.scalar_one_or_none()
            if not job or job.status not in (ProcessingStatus.QUEUED, ProcessingStatus.PROCESSING):
                return

            doc_res = await db.execute(
                select(Document).where(
                    Document.id == job.document_id, Document.deleted_at.is_(None)
                )
            )
            document = doc_res.scalar_one_or_none()
            if not document:
                job.status = ProcessingStatus.FAILED
                job.error_code = "DOCUMENT_NOT_FOUND"
                job.error_message = "Document was deleted or not found before processing."
                job.completed_at = datetime.now(timezone.utc)
                await db.commit()
                return

            # Mark in progress
            job.status = ProcessingStatus.PROCESSING
            job.started_at = datetime.now(timezone.utc)
            job.attempts += 1
            document.status = DocumentStatus.PROCESSING
            await db.commit()

            ollama_service = OllamaService()
            storage = get_storage_backend()

            temp_local_file: Optional[Path] = None

            try:
                # 1. Verify Ollama reachable
                if not await ollama_service.check_connection():
                    raise OllamaServiceException(
                        code="OLLAMA_UNAVAILABLE",
                        message=f"Cannot connect to Ollama at {settings.OLLAMA_BASE_URL}.",
                    )

                # 2. Verify model availability
                if not await ollama_service.check_model_available():
                    raise OllamaServiceException(
                        code="MODEL_NOT_FOUND",
                        message=f"Model '{settings.OLLAMA_MODEL}' is not available in Ollama.",
                    )

                # 3. Stream document from storage to a local temporary file for page parsing
                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=document.file_extension
                ) as tmp_f:
                    temp_local_file = Path(tmp_f.name)

                hasher = hashlib.sha256()
                async with await anyio.open_file(temp_local_file, mode="wb") as out_f:
                    async for chunk in storage.get_stream(document.storage_key):
                        hasher.update(chunk)
                        await out_f.write(chunk)

                # Verify hash integrity
                if hasher.hexdigest() != document.sha256_hash:
                    raise OllamaServiceException(
                        code="STORAGE_ERROR",
                        message="Stored file SHA-256 hash mismatch.",
                    )

                # 4. Preprocess file into normalized page image buffers
                pages_bytes = OcrService.preprocess_document_to_pages(
                    temp_local_file, document.file_extension
                )

                # 5. Clean any stale OCR results for this document
                await db.execute(
                    delete(OCRResult).where(OCRResult.document_id == document.id)
                )
                await db.commit()

                # 6. Execute DeepSeek OCR on each page and persist results
                for idx, page_data in enumerate(pages_bytes):
                    page_num = idx + 1
                    text, duration_ms = await OcrService.process_page(
                        ollama_service=ollama_service,
                        page_bytes=page_data,
                        page_number=page_num,
                    )

                    ocr_res = OCRResult(
                        id=uuid.uuid4(),
                        document_id=document.id,
                        page_number=page_num,
                        text=text,
                        model_name=settings.OLLAMA_MODEL,
                        processing_time_ms=duration_ms,
                    )
                    db.add(ocr_res)
                    await db.commit()

                # 7. Mark processing successfully completed
                document.status = DocumentStatus.PROCESSED
                document.processed_at = datetime.now(timezone.utc)
                job.status = ProcessingStatus.COMPLETED
                job.completed_at = datetime.now(timezone.utc)
                job.error_code = None
                job.error_message = None
                await db.commit()

                logger.info(
                    "Document %s OCR successfully completed (%d pages).",
                    document.id,
                    len(pages_bytes),
                )

            except OllamaServiceException as ose:
                logger.error("Document %s OCR failed: %s", document.id, ose)
                document.status = DocumentStatus.FAILED
                job.status = ProcessingStatus.FAILED
                job.error_code = ose.code
                job.error_message = ose.message
                job.completed_at = datetime.now(timezone.utc)
                await db.commit()

            except Exception as ex:
                logger.exception("Unexpected error processing document %s", document.id)
                document.status = DocumentStatus.FAILED
                job.status = ProcessingStatus.FAILED
                job.error_code = "UNKNOWN_ERROR"
                job.error_message = f"Processing error: {str(ex)}"
                job.completed_at = datetime.now(timezone.utc)
                await db.commit()

            finally:
                if temp_local_file and temp_local_file.exists():
                    try:
                        temp_local_file.unlink()
                    except Exception:
                        pass
