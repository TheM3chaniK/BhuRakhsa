from fastapi import HTTPException
import pytest

from app.services.file_validation_service import FileValidationService


def test_filename_sanitization() -> None:
    """Verify that path traversal and malicious characters are stripped from original filenames."""
    assert FileValidationService.sanitize_filename("../../evil.pdf") == "evil.pdf"
    assert FileValidationService.sanitize_filename("..\\..\\evil.pdf") == "evil.pdf"
    assert FileValidationService.sanitize_filename("/etc/passwd.pdf") == "passwd.pdf"
    assert FileValidationService.sanitize_filename("normal_deed.pdf") == "normal_deed.pdf"
    assert FileValidationService.sanitize_filename("") == "document.pdf"


def test_extension_validation() -> None:
    """Verify supported extensions are allowed and unsupported are rejected with 415."""
    assert FileValidationService.validate_extension("doc.pdf") == ".pdf"
    assert FileValidationService.validate_extension("doc.PDF") == ".pdf"
    assert FileValidationService.validate_extension("image.jpg") == ".jpg"
    assert FileValidationService.validate_extension("image.jpeg") == ".jpeg"
    assert FileValidationService.validate_extension("scan.png") == ".png"

    with pytest.raises(HTTPException) as exc_exe:
        FileValidationService.validate_extension("malicious.exe")
    assert exc_exe.value.status_code == 415

    with pytest.raises(HTTPException) as exc_sh:
        FileValidationService.validate_extension("script.sh")
    assert exc_sh.value.status_code == 415


def test_magic_bytes_validation() -> None:
    """Verify binary header signatures for PDF, JPEG, and PNG."""
    # Valid signatures
    FileValidationService.validate_magic_bytes(b"%PDF-1.7 header content", ".pdf")
    FileValidationService.validate_magic_bytes(b"\xff\xd8\xff\xe0\x00\x10JFIF", ".jpg")
    FileValidationService.validate_magic_bytes(b"\xff\xd8\xff\xe1\x00\x10Exif", ".jpeg")
    FileValidationService.validate_magic_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR", ".png")

    # Invalid signatures (e.g. text file pretending to be PDF)
    with pytest.raises(HTTPException) as exc_pdf:
        FileValidationService.validate_magic_bytes(b"Plain text disguised as PDF", ".pdf")
    assert exc_pdf.value.status_code == 400

    # Short/empty content
    with pytest.raises(HTTPException) as exc_short:
        FileValidationService.validate_magic_bytes(b"hi", ".pdf")
    assert exc_short.value.status_code == 400


def test_size_validation() -> None:
    """Verify size limits enforcement."""
    # Zero bytes -> 400
    with pytest.raises(HTTPException) as exc_empty:
        FileValidationService.validate_size(0)
    assert exc_empty.value.status_code == 400

    # Valid size
    FileValidationService.validate_size(1024 * 1024)  # 1MB

    # Oversized -> 413
    with pytest.raises(HTTPException) as exc_large:
        FileValidationService.validate_size(30 * 1024 * 1024)  # 30MB > 25MB default
    assert exc_large.value.status_code == 413
