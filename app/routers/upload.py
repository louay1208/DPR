"""File upload endpoints."""

from __future__ import annotations

import shutil
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from app.config import ALLOWED_EXTENSIONS, MAX_UPLOAD_SIZE, UPLOAD_DIR
from app.models.schemas import FileInfo, FileListResponse, ProcessingStatus
from app.services.logger import LogService

router = APIRouter(prefix="/api/files", tags=["files"])

# In-memory file registry (rebuilt from disk on startup)
_file_registry: dict[str, FileInfo] = {}


def _rebuild_registry_from_disk() -> None:
    """Scan the uploads directory and rebuild the file registry.

    Handles upload-prefixed filenames (12-char hex + underscore).
    Called once at module load to survive server restarts.
    """
    if not UPLOAD_DIR.exists():
        return

    for f in UPLOAD_DIR.iterdir():
        if not f.is_file():
            continue
        ext = f.suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            continue

        stem = f.stem
        # Extract the file_id and original_name from "a1b2c3d4e5f6_OriginalName.xlsx"
        if len(stem) > 13 and stem[12] == "_":
            prefix = stem[:12]
            try:
                int(prefix, 16)  # verify it's hex
                file_id = prefix
                original_name = stem[13:] + f.suffix
            except ValueError:
                file_id = stem[:12]
                original_name = f.name
        else:
            file_id = stem[:12] if len(stem) >= 12 else stem
            original_name = f.name

        if file_id not in _file_registry:
            stat = f.stat()
            _file_registry[file_id] = FileInfo(
                id=file_id,
                filename=f.name,
                original_name=original_name,
                size=stat.st_size,
                uploaded_at=datetime.fromtimestamp(stat.st_mtime),
                status=ProcessingStatus.COMPLETED,
            )


# Rebuild on module load (server start / reload)
_rebuild_registry_from_disk()


@router.post("", response_model=list[FileInfo])
async def upload_files(files: list[UploadFile]) -> list[FileInfo]:
    """Upload one or more DPR files (batch)."""
    results = []
    for f in files:
        info = await _save_single_file(f)
        if info:
            results.append(info)
    if not results:
        raise HTTPException(status_code=400, detail="No valid files uploaded")
    return results


@router.post("/single", response_model=FileInfo)
async def upload_single_file(file: UploadFile) -> FileInfo:
    """Upload a single DPR file (used by the web UI)."""
    info = await _save_single_file(file)
    if not info:
        raise HTTPException(status_code=400, detail="Invalid file")
    return info


async def _save_single_file(file: UploadFile) -> FileInfo | None:
    """Save one uploaded file, returning FileInfo or None if invalid."""
    logger = LogService.get()

    # Validate extension
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        await logger.warning(
            f"Rejected {file.filename}: unsupported format ({ext})",
            source="upload",
        )
        return None

    # Validate size
    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        await logger.warning(
            f"Rejected {file.filename}: exceeds size limit", source="upload"
        )
        return None

    # Save file
    file_id = uuid.uuid4().hex[:12]
    safe_name = f"{file_id}_{file.filename}"
    dest = UPLOAD_DIR / safe_name

    with open(dest, "wb") as f:
        f.write(content)

    info = FileInfo(
        id=file_id,
        filename=safe_name,
        original_name=file.filename or "unknown",
        size=len(content),
        uploaded_at=datetime.now(),
        status=ProcessingStatus.PENDING,
    )
    _file_registry[file_id] = info

    await logger.success(
        f"Uploaded: {file.filename} ({len(content):,} bytes)",
        source="upload",
    )
    return info



@router.get("", response_model=FileListResponse)
async def list_files() -> FileListResponse:
    """List all uploaded files."""
    files = list(_file_registry.values())
    return FileListResponse(files=files, total=len(files))


@router.delete("/{file_id}")
async def delete_file(file_id: str) -> JSONResponse:
    """Delete an uploaded file."""
    logger = LogService.get()

    info = _file_registry.get(file_id)
    if not info:
        raise HTTPException(status_code=404, detail="File not found")

    # Remove from disk
    filepath = UPLOAD_DIR / info.filename
    if filepath.exists():
        filepath.unlink()

    del _file_registry[file_id]
    await logger.info(f"Deleted: {info.original_name}", source="upload")

    return JSONResponse({"status": "deleted", "id": file_id})


@router.delete("")
async def delete_all_files() -> JSONResponse:
    """Delete all uploaded files."""
    logger = LogService.get()
    count = len(_file_registry)

    for info in _file_registry.values():
        filepath = UPLOAD_DIR / info.filename
        if filepath.exists():
            filepath.unlink()

    _file_registry.clear()
    await logger.info(f"Cleared {count} files", source="upload")

    return JSONResponse({"status": "cleared", "count": count})
