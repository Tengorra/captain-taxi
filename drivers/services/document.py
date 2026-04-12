"""Document storage — saves uploaded files to local disk (swap for S3 in prod)."""
import os
import uuid
import aiofiles
from pathlib import Path
from fastapi import UploadFile
from config import settings

UPLOAD_DIR = Path("uploads/driver_docs")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".heic"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


async def save_document(driver_id: int, doc_type: str, file: UploadFile) -> str:
    """
    Save uploaded document to disk.
    Returns the storage path (relative to app root).
    Raises ValueError if file type or size is invalid.
    """
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"File type {ext} not allowed. Accepted: {', '.join(ALLOWED_EXTENSIONS)}")

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise ValueError("File too large (max 10 MB)")

    filename = f"{uuid.uuid4().hex}{ext}"
    driver_dir = UPLOAD_DIR / str(driver_id) / doc_type
    driver_dir.mkdir(parents=True, exist_ok=True)
    full_path = driver_dir / filename

    async with aiofiles.open(full_path, "wb") as f:
        await f.write(contents)

    return str(full_path)


def get_document_url(storage_path: str) -> str:
    """Return a URL to download the document (via the /documents endpoint)."""
    return f"{settings.base_url}/api/drivers/documents/file?path={storage_path}"
