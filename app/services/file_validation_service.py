from pathlib import Path
import re
from typing import ClassVar, Set

from fastapi import HTTPException, status

from app.core.config import settings


class FileValidationService:
    """Service providing strict file validation: extension whitelist, MIME type, magic-byte signatures, size limits, and filename sanitization."""

    ALLOWED_EXTENSIONS: ClassVar[Set[str]] = {".pdf", ".jpg", ".jpeg", ".png"}

    ALLOWED_MIME_TYPES: ClassVar[Set[str]] = {
        "application/pdf",
        "image/jpeg",
        "image/png",
    }

    # Standard magic byte signatures
    MAGIC_SIGNATURES: ClassVar[dict[str, list[bytes]]] = {
        ".pdf": [b"%PDF-"],
        ".jpg": [b"\xff\xd8\xff"],
        ".jpeg": [b"\xff\xd8\xff"],
        ".png": [b"\x89PNG\r\n\x1a\n"],
    }

    MIME_MAP: ClassVar[dict[str, str]] = {
        ".pdf": "application/pdf",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
    }

    @classmethod
    def sanitize_filename(cls, original_filename: str) -> str:
        """Strip directory paths (POSIX and Windows), null bytes, and traversal characters to produce a safe base filename."""
        if not original_filename:
            return "document.pdf"

        # Normalize backslashes to forward slashes before getting the basename
        normalized = original_filename.replace("\\", "/")
        base_name = Path(normalized).name

        # Remove any remaining invalid/traversal characters and null bytes
        clean_name = re.sub(r'[\x00/\\:*?"<>|]', "_", base_name).strip()

        return clean_name if clean_name else "document.pdf"

    @classmethod
    def validate_extension(cls, filename: str) -> str:
        """Validate and normalize file extension against allowed types."""
        normalized = filename.replace("\\", "/")
        ext = Path(normalized).suffix.lower()
        if not ext or ext not in cls.ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"Unsupported file format '{ext}'. Allowed formats: PDF, JPEG, JPG, PNG.",
            )
        return ext

    @classmethod
    def validate_mime_type(cls, mime_type: str, extension: str) -> str:
        """Normalize and validate client-supplied MIME type against allowed MIME types and extension."""
        normalized_mime = mime_type.strip().lower() if mime_type else ""

        expected_mime = cls.MIME_MAP.get(extension)
        if normalized_mime and normalized_mime not in cls.ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"Unsupported MIME type '{normalized_mime}'.",
            )

        return expected_mime if expected_mime else normalized_mime

    @classmethod
    def validate_magic_bytes(cls, header: bytes, extension: str) -> None:
        """Verify binary content header against expected magic byte signatures."""
        if len(header) < 4:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File is too short or empty to determine signature.",
            )

        signatures = cls.MAGIC_SIGNATURES.get(extension, [])
        matches = any(header.startswith(sig) for sig in signatures)
        if not matches:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File signature does not match declared extension '{extension}'.",
            )

    @classmethod
    def validate_size(cls, total_bytes: int) -> None:
        """Enforce non-empty content and maximum upload size limits."""
        if total_bytes <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty.",
            )

        if total_bytes > settings.max_upload_size_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"File size exceeds the maximum limit of {settings.MAX_UPLOAD_SIZE_MB}MB.",
            )
