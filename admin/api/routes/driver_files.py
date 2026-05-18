"""HR-style file uploads for drivers (Police Disclosure, Agreement, Photo ID,
Licence Photo/Paper, Proof of Address, PCO Licence, Insurance, …).

Compliance-relevant docs (e.g. SGI insurance, taxi license) continue to live
in the `documents` table so the traffic-light overview stays accurate. This
table only holds files the iCabbi driver record can attach but that don't
drive auto-suspension."""
import os
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ...db.database import get_db
from ...db.models import Driver, DriverFile


router = APIRouter(prefix="/drivers", tags=["driver-files"])


ALLOWED_TYPES = {
    "police_disclosure", "agreement", "proof_of_address", "photo_id",
    "licence_photo", "licence_paper", "pco_licence", "insurance", "other",
}

# Files are written under /data/driver_files/<driver_id>/. Override with
# DRIVER_FILE_ROOT when running locally on macOS.
STORAGE_ROOT = os.getenv("DRIVER_FILE_ROOT", "/data/driver_files")


def _safe_filename(name: str) -> str:
    # Strip any path component a browser sends as filename.
    return os.path.basename(name).replace("/", "_").replace("\\", "_")[:200]


@router.post("/{driver_id}/files")
async def upload_driver_file(
    driver_id: str,
    file_type: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if file_type not in ALLOWED_TYPES:
        raise HTTPException(400, f"file_type must be one of {sorted(ALLOWED_TYPES)}")
    driver = db.query(Driver).filter_by(id=driver_id).first()
    if not driver:
        raise HTTPException(404, "Driver not found")

    safe_name = _safe_filename(file.filename or f"{file_type}.bin")
    driver_dir = os.path.join(STORAGE_ROOT, driver_id)
    os.makedirs(driver_dir, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    storage_path = os.path.join(driver_dir, f"{file_type}_{ts}_{safe_name}")

    content = await file.read()
    with open(storage_path, "wb") as fh:
        fh.write(content)

    row = DriverFile(
        id=str(uuid.uuid4()),
        driver_id=driver_id,
        file_type=file_type,
        filename=safe_name,
        storage_path=storage_path,
        size_bytes=len(content),
        content_type=file.content_type,
        uploaded_at=datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {
        "id": row.id,
        "type": row.file_type,
        "filename": row.filename,
        "content_type": row.content_type,
        "size_bytes": row.size_bytes,
        "uploaded_at": row.uploaded_at.isoformat(),
    }


@router.get("/{driver_id}/files")
def list_driver_files(driver_id: str, db: Session = Depends(get_db)):
    rows = db.query(DriverFile).filter(DriverFile.driver_id == driver_id).all()
    return [
        {
            "id": f.id,
            "type": f.file_type,
            "filename": f.filename,
            "content_type": f.content_type,
            "size_bytes": f.size_bytes,
            "uploaded_at": f.uploaded_at.isoformat() if f.uploaded_at else None,
        }
        for f in rows
    ]


@router.get("/{driver_id}/files/{file_id}/download")
def download_driver_file(driver_id: str, file_id: str, db: Session = Depends(get_db)):
    row = db.query(DriverFile).filter_by(id=file_id, driver_id=driver_id).first()
    if not row or not os.path.exists(row.storage_path):
        raise HTTPException(404, "File not found")
    return FileResponse(row.storage_path, filename=row.filename,
                        media_type=row.content_type or "application/octet-stream")


@router.delete("/{driver_id}/files/{file_id}")
def delete_driver_file(driver_id: str, file_id: str, db: Session = Depends(get_db)):
    row = db.query(DriverFile).filter_by(id=file_id, driver_id=driver_id).first()
    if not row:
        raise HTTPException(404, "File not found")
    try:
        os.remove(row.storage_path)
    except OSError:
        # File already gone from disk; still drop the row so the UI clears.
        pass
    db.delete(row)
    db.commit()
    return {"ok": True}
