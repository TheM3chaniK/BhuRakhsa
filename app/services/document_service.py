from datetime import datetime, timezone
import hashlib
from pathlib import Path
import tempfile
from typing import AsyncGenerator, Sequence
import uuid

import anyio
from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import logger
from app.models.case import Case
from app.models.document import Document
from app.models.enums import CaseStatus, DocumentStatus, UserRole
from app.models.user import User
from app.services.case_access_service import CaseAccessService
from app.services.file_validation_service import FileValidationService
from app.storage import get_storage_backend


class DocumentService:
    """Service handling secure document upload, streaming hashing, storage persistence, and document retrieval."""

    @staticmethod
    async def upload_document(
        db: AsyncSession, case_id: uuid.UUID, user: User, upload_file: UploadFile
    ) -> Document:
        """Process, validate, hash, store, and record an uploaded document."""
        # 1. Fetch and validate case
        case_res = await db.execute(select(Case).where(Case.id == case_id))
        case = case_res.scalar_one_or_none()
        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Case not found.",
            )

        # 2. Enforce civilian ownership
        if user.role != UserRole.CIVILIAN or case.created_by != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to upload documents to this case.",
            )

        # 3. Enforce case status
        if case.status not in [CaseStatus.DRAFT, CaseStatus.SUBMITTED]:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Documents cannot be uploaded to cases in terminal or non-editable status.",
            )

        # 4. Filename & extension validation
        original_filename = FileValidationService.sanitize_filename(
            upload_file.filename or "document.pdf"
        )
        ext = FileValidationService.validate_extension(original_filename)
        mime_type = FileValidationService.validate_mime_type(
            upload_file.content_type or "", ext
        )

        # 5. Stream upload to a temporary file while hashing and verifying size
        storage = get_storage_backend()
        hasher = hashlib.sha256()
        total_bytes = 0
        header_bytes = b""

        with tempfile.NamedTemporaryFile(delete=False) as temp_f:
            temp_path = Path(temp_f.name)

        try:
            async with await anyio.open_file(temp_path, mode="wb") as out_f:
                while True:
                    chunk = await upload_file.read(64 * 1024)
                    if not chunk:
                        break

                    if len(header_bytes) < 32:
                        header_bytes += chunk[: 32 - len(header_bytes)]

                    total_bytes += len(chunk)
                    if total_bytes > settings.max_upload_size_bytes:
                        raise HTTPException(
                            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                            detail=f"File size exceeds maximum limit of {settings.MAX_UPLOAD_SIZE_MB}MB.",
                        )

                    hasher.update(chunk)
                    await out_f.write(chunk)

            # 6. Validate content size and magic bytes
            FileValidationService.validate_size(total_bytes)
            FileValidationService.validate_magic_bytes(header_bytes, ext)

            # 7. Generate deterministic storage layout
            doc_id = uuid.uuid4()
            stored_filename = f"{doc_id}{ext}"
            storage_key = f"cases/{case.id}/documents/{doc_id}/original/{stored_filename}"
            sha256_hex = hasher.hexdigest()

            # 8. Persist file to storage backend
            await storage.save_file(temp_path, storage_key)

            # 9. Create database record
            document = Document(
                id=doc_id,
                case_id=case.id,
                original_filename=original_filename,
                stored_filename=stored_filename,
                mime_type=mime_type,
                file_extension=ext,
                file_size=total_bytes,
                sha256_hash=sha256_hex,
                storage_backend=settings.STORAGE_BACKEND,
                storage_key=storage_key,
                status=DocumentStatus.UPLOADED,
                uploaded_by=user.id,
            )
            db.add(document)
            try:
                await db.commit()
                await db.refresh(document)
            except IntegrityError:
                await db.rollback()
                # Clean up stored file on database transaction failure
                await storage.delete(storage_key)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Database error while recording document metadata.",
                )

            return document

        except Exception:
            # Clean up temp file on error
            if temp_path.exists():
                temp_path.unlink()
            raise

    @staticmethod
    async def get_document(
        db: AsyncSession, document_id: uuid.UUID, user: User
    ) -> Document:
        """Retrieve document metadata with authorization check."""
        query = select(Document).where(
            Document.id == document_id, Document.deleted_at.is_(None)
        )
        result = await db.execute(query)
        doc = result.scalar_one_or_none()
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found.",
            )

        case_res = await db.execute(select(Case).where(Case.id == doc.case_id))
        case = case_res.scalar_one_or_none()
        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Associated case not found.",
            )

        await CaseAccessService.verify_case_access(db, user, case)
        return doc

    @staticmethod
    async def list_documents_for_case(
        db: AsyncSession, case_id: uuid.UUID, user: User
    ) -> Sequence[Document]:
        """List all active documents belonging to a case with access verification."""
        case_res = await db.execute(select(Case).where(Case.id == case_id))
        case = case_res.scalar_one_or_none()
        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Case not found.",
            )

        await CaseAccessService.verify_case_access(db, user, case)

        query = (
            select(Document)
            .where(Document.case_id == case_id, Document.deleted_at.is_(None))
            .order_by(Document.created_at.asc())
        )
        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def download_document(
        db: AsyncSession, document_id: uuid.UUID, user: User
    ) -> tuple[Document, AsyncGenerator[bytes, None]]:
        """Retrieve document metadata and stream generator for download."""
        doc = await DocumentService.get_document(db, document_id, user)
        storage = get_storage_backend()

        if not await storage.exists(doc.storage_key):
            logger.error("Document file missing from storage: %s", doc.storage_key)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document file content not found in storage.",
            )

        stream = storage.get_stream(doc.storage_key)
        return doc, stream

    @staticmethod
    async def delete_document(
        db: AsyncSession, document_id: uuid.UUID, user: User
    ) -> None:
        """Soft delete a document (Civilian case owner only, while case is in DRAFT)."""
        query = select(Document).where(
            Document.id == document_id, Document.deleted_at.is_(None)
        )
        result = await db.execute(query)
        doc = result.scalar_one_or_none()
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found.",
            )

        case_res = await db.execute(select(Case).where(Case.id == doc.case_id))
        case = case_res.scalar_one_or_none()
        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Associated case not found.",
            )

        if user.role != UserRole.CIVILIAN or case.created_by != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the case owner can delete this document.",
            )

        if case.status != CaseStatus.DRAFT:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Documents can only be deleted while the case is in draft status.",
            )

        if doc.status == DocumentStatus.PROCESSING:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Document is currently being processed and cannot be deleted.",
            )

        doc.deleted_at = datetime.now(timezone.utc)
        doc.updated_at = datetime.now(timezone.utc)
        await db.commit()
