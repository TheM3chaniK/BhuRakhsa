from pathlib import Path
import tempfile
import pytest

from app.storage.local import LocalStorageBackend


@pytest.mark.anyio
async def test_local_storage_backend_lifecycle(tmp_path: Path) -> None:
    """Verify local storage file operations: save, exists, get_size, stream, delete."""
    storage = LocalStorageBackend(root_dir=tmp_path)

    # 1. Create a temp file to simulate an upload
    temp_file = tmp_path / "temp_upload.tmp"
    sample_data = b"Property deed binary data content"
    temp_file.write_bytes(sample_data)

    storage_key = "cases/case-123/documents/doc-456/original/deed.pdf"

    # 2. Save file
    saved_size = await storage.save_file(temp_file, storage_key)
    assert saved_size == len(sample_data)
    assert not temp_file.exists()  # Temp file was moved

    # 3. Check existence and size
    assert await storage.exists(storage_key) is True
    assert await storage.get_size(storage_key) == len(sample_data)

    # 4. Stream content
    streamed_data = b""
    async for chunk in storage.get_stream(storage_key):
        streamed_data += chunk
    assert streamed_data == sample_data

    # 5. Delete file
    deleted = await storage.delete(storage_key)
    assert deleted is True
    assert await storage.exists(storage_key) is False


@pytest.mark.anyio
async def test_path_traversal_prevention(tmp_path: Path) -> None:
    """Verify LocalStorageBackend strictly prevents path traversal outside the root directory."""
    storage = LocalStorageBackend(root_dir=tmp_path)

    # Attempting to resolve a path that escapes root_path raises PermissionError
    with pytest.raises(PermissionError):
        storage._resolve_path("../../etc/passwd")

    with pytest.raises(PermissionError):
        storage._resolve_path("../outside.pdf")
