import asyncio
from typing import Optional
import uuid

from app.core.config import settings
from app.core.logging import logger
from app.services.document_processing_service import DocumentProcessingService
from app.services.extraction_service import ExtractionService


class DocumentWorker:
    """Async background worker orchestrating OCR, structured extraction, and validation runs with bounded concurrency."""

    _semaphore: Optional[asyncio.Semaphore] = None

    @classmethod
    def _get_semaphore(cls) -> asyncio.Semaphore:
        if cls._semaphore is None:
            cls._semaphore = asyncio.Semaphore(settings.OCR_MAX_CONCURRENCY)
        return cls._semaphore

    @classmethod
    async def _execute_job(cls, job_id: uuid.UUID) -> None:
        """Run document OCR processing inside concurrency semaphore."""
        sem = cls._get_semaphore()
        async with sem:
            logger.info("Starting background OCR processing for job %s...", job_id)
            try:
                await DocumentProcessingService.execute_processing_job(job_id)
            except Exception as e:
                logger.exception("Uncaught exception in background OCR worker for job %s: %s", job_id, e)

    @classmethod
    async def _execute_extraction_job(cls, job_id: uuid.UUID) -> None:
        """Run document field extraction inside concurrency semaphore."""
        sem = cls._get_semaphore()
        async with sem:
            logger.info("Starting background field extraction for job %s...", job_id)
            try:
                await ExtractionService.execute_extraction_job(job_id)
            except Exception as e:
                logger.exception("Uncaught exception in background extraction worker for job %s: %s", job_id, e)

    @classmethod
    async def _execute_validation_run(cls, run_id: uuid.UUID) -> None:
        """Run external reference validation session inside concurrency semaphore."""
        from app.services.property_profile_service import PropertyProfileService
        sem = cls._get_semaphore()
        async with sem:
            logger.info("Starting background validation execution for run %s...", run_id)
            try:
                await PropertyProfileService.execute_validation_run(run_id)
            except Exception as e:
                logger.exception("Uncaught exception in background validation worker for run %s: %s", run_id, e)

    @classmethod
    def enqueue_job(cls, job_id: uuid.UUID) -> None:
        """Dispatch asynchronous background OCR task."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(cls._execute_job(job_id))
        except RuntimeError:
            asyncio.run(cls._execute_job(job_id))

    @classmethod
    def enqueue_extraction_job(cls, job_id: uuid.UUID) -> None:
        """Dispatch asynchronous background field extraction task."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(cls._execute_extraction_job(job_id))
        except RuntimeError:
            asyncio.run(cls._execute_extraction_job(job_id))

    @classmethod
    def enqueue_validation_run(cls, run_id: uuid.UUID) -> None:
        """Dispatch asynchronous background validation task."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(cls._execute_validation_run(run_id))
        except RuntimeError:
            asyncio.run(cls._execute_validation_run(run_id))
