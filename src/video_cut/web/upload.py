"""File upload handling for the web interface."""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Optional

from fastapi import UploadFile


# 允许的上传文件类型
ALLOWED_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv", ".webm"}
# 最大文件大小 (5GB)
MAX_FILE_SIZE = 5 * 1024 * 1024 * 1024


def validate_upload_file(filename: str) -> bool:
    """Validate file extension."""
    ext = Path(filename).suffix.lower()
    return ext in ALLOWED_EXTENSIONS


async def save_uploaded_file(
    upload_dir: Path, file: UploadFile, chunk_size: int = 1024 * 1024
) -> tuple[Path, int]:
    """Save uploaded file to upload directory.

    Returns:
        Tuple of (saved_path, file_size)
    """
    # Validate file type
    if not validate_upload_file(file.filename):
        raise ValueError(
            f"Unsupported file type: {file.filename}. "
            f"Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # Generate unique filename to avoid conflicts
    original_name = Path(file.filename).stem
    extension = Path(file.filename).suffix
    unique_filename = f"{original_name}_{uuid.uuid4().hex[:8]}{extension}"

    saved_path = upload_dir / unique_filename
    saved_path.parent.mkdir(parents=True, exist_ok=True)

    # Save file in chunks
    file_size = 0
    try:
        with open(saved_path, "wb") as f:
            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break
                file_size += len(chunk)

                # Check file size limit
                if file_size > MAX_FILE_SIZE:
                    raise ValueError(
                        f"File too large: {file_size / 1024 / 1024:.2f}MB. "
                        f"Max size: {MAX_FILE_SIZE / 1024 / 1024}MB"
                    )

                f.write(chunk)
    except ValueError:
        # Clean up on error
        import time
        time.sleep(0.1)  # Give OS time to release file handle
        saved_path.unlink(missing_ok=True)
        raise

    return saved_path, file_size


def get_upload_dir(output_dir: Path) -> Path:
    """Get or create upload directory."""
    upload_dir = output_dir / "_uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


def cleanup_old_uploads(upload_dir: Path, max_age_hours: int = 24) -> int:
    """Clean up uploaded files older than specified hours.

    Returns:
        Number of files cleaned up
    """
    import time

    now = time.time()
    max_age_seconds = max_age_hours * 3600
    cleaned = 0

    for file_path in upload_dir.glob("*"):
        if file_path.is_file():
            file_age = now - file_path.stat().st_mtime
            if file_age > max_age_seconds:
                try:
                    file_path.unlink()
                    cleaned += 1
                except OSError:
                    pass

    return cleaned
