"""
Document CRUD — upload, update, list compliance documents.
"""
from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import Document, DocumentStatus, Driver, DriverStatus
from compliance.database import get_db
from compliance.services.suspension import reinstate_driver

router = APIRouter(prefix="/compliance/documents", tags=["documents"])


class DocumentCreate(BaseModel):
    entity_id: str
    entity_type: str          # driver, vehicle, company
    doc_type: str
    expiry_date: Optional[date] = None
    file_path: Optional[str] = None
    notes: Optional[str] = None


class DocumentUpdate(BaseModel):
    expiry_date: Optional[date] = None
    file_path: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None


@router.post("/")
async def create_document(data: DocumentCreate, db: AsyncSession = Depends(get_db)):
    doc = Document(
        entity_id=data.entity_id,
        entity_type=data.entity_type,
        doc_type=data.doc_type,
        expiry_date=data.expiry_date,
        file_path=data.file_path,
        notes=data.notes,
        status=_compute_status(data.expiry_date),
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return doc


@router.put("/{doc_id}")
async def update_document(doc_id: str, data: DocumentUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(404, "Document not found")

    if data.expiry_date is not None:
        doc.expiry_date = data.expiry_date
        doc.status = _compute_status(data.expiry_date)
    if data.file_path is not None:
        doc.file_path = data.file_path
    if data.notes is not None:
        doc.notes = data.notes

    await db.commit()

    # If driver was suspended for this doc type and now it's valid, consider reinstatement
    if doc.entity_type == "driver" and doc.status == DocumentStatus.VALID:
        await _check_reinstate(db, doc.entity_id)

    return doc


@router.get("/entity/{entity_type}/{entity_id}")
async def get_entity_documents(
    entity_type: str, entity_id: str, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Document).where(
            Document.entity_id == entity_id,
            Document.entity_type == entity_type,
        )
    )
    return result.scalars().all()


@router.get("/expiring")
async def get_expiring_documents(days: int = 30, db: AsyncSession = Depends(get_db)):
    from datetime import timedelta
    cutoff = date.today() + timedelta(days=days)
    result = await db.execute(
        select(Document).where(
            Document.expiry_date <= cutoff,
            Document.expiry_date >= date.today(),
        )
    )
    return result.scalars().all()


@router.get("/expired")
async def get_expired_documents(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Document).where(Document.status == DocumentStatus.EXPIRED)
    )
    return result.scalars().all()


def _compute_status(expiry_date) -> str:
    from datetime import timedelta
    today = date.today()
    if expiry_date is None:
        return DocumentStatus.MISSING
    if expiry_date < today:
        return DocumentStatus.EXPIRED
    if expiry_date <= today + timedelta(days=30):
        return DocumentStatus.EXPIRING_SOON
    return DocumentStatus.VALID


async def _check_reinstate(db: AsyncSession, driver_id: str):
    """Reinstate driver if all mandatory docs are now valid."""
    from compliance.services.sweep import REQUIRED_DRIVER_DOCS
    result = await db.execute(
        select(Document).where(
            Document.entity_id == driver_id,
            Document.entity_type == "driver",
            Document.doc_type.in_(REQUIRED_DRIVER_DOCS),
        )
    )
    docs = result.scalars().all()
    all_valid = all(d.status == DocumentStatus.VALID for d in docs)

    if all_valid and len(docs) == len(REQUIRED_DRIVER_DOCS):
        driver_result = await db.execute(
            select(Driver).where(
                Driver.id == driver_id,
                Driver.status == DriverStatus.SUSPENDED,
            )
        )
        driver = driver_result.scalar_one_or_none()
        if driver:
            await reinstate_driver(db, driver_id)
