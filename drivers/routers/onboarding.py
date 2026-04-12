"""Onboarding step management endpoints."""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.driver import Driver, OnboardingStep, OnboardingStepName, DriverDocument, DocumentType
from agents.onboarding_agent import complete_step, get_steps, calculate_completion
from services.document import save_document

router = APIRouter(prefix="/drivers", tags=["onboarding"])


class StepCompleteRequest(BaseModel):
    step: OnboardingStepName
    notes: Optional[str] = None
    data: Optional[dict] = None


class StepResponse(BaseModel):
    id: int
    step: str
    completed: bool
    completed_at: Optional[datetime]
    notes: Optional[str]

    class Config:
        from_attributes = True


@router.get("/{driver_id}/onboarding")
async def get_onboarding_status(driver_id: int, db: AsyncSession = Depends(get_db)):
    """Get onboarding progress for a driver."""
    result = await db.execute(select(Driver).where(Driver.id == driver_id))
    driver = result.scalar_one_or_none()
    if not driver:
        raise HTTPException(404, "Driver not found")

    steps = await get_steps(driver_id, db)
    completion = await calculate_completion(driver_id, db)

    return {
        "driver_id": driver_id,
        "driver_name": driver.full_name,
        "completion_pct": round(completion * 100, 1),
        "status": driver.status.value,
        "steps": [
            {
                "step": s.step.value,
                "label": s.step.value.replace("_", " ").title(),
                "completed": s.completed,
                "completed_at": s.completed_at,
            }
            for s in steps
        ],
    }


@router.post("/{driver_id}/onboarding/complete-step")
async def mark_step_complete(
    driver_id: int,
    payload: StepCompleteRequest,
    db: AsyncSession = Depends(get_db),
):
    """Mark an onboarding step as complete (admin / portal use)."""
    result = await db.execute(select(Driver).where(Driver.id == driver_id))
    driver = result.scalar_one_or_none()
    if not driver:
        raise HTTPException(404, "Driver not found")

    try:
        step = await complete_step(driver, payload.step, db, payload.notes, payload.data)
    except ValueError as e:
        raise HTTPException(400, str(e))

    completion = await calculate_completion(driver_id, db)
    return {
        "step": step.step.value,
        "completed": step.completed,
        "onboarding_completion": round(completion * 100, 1),
    }


@router.post("/{driver_id}/documents/upload")
async def upload_document(
    driver_id: int,
    doc_type: DocumentType = Form(...),
    expiry_date: Optional[str] = Form(None),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload a driver document (licence, insurance, etc.)."""
    result = await db.execute(select(Driver).where(Driver.id == driver_id))
    driver = result.scalar_one_or_none()
    if not driver:
        raise HTTPException(404, "Driver not found")

    try:
        storage_path = await save_document(driver_id, doc_type.value, file)
    except ValueError as e:
        raise HTTPException(400, str(e))

    expiry = None
    if expiry_date:
        try:
            expiry = datetime.fromisoformat(expiry_date)
        except ValueError:
            raise HTTPException(400, "Invalid expiry_date format (use ISO 8601)")

    doc = DriverDocument(
        driver_id=driver_id,
        doc_type=doc_type,
        filename=file.filename,
        storage_path=storage_path,
        expiry_date=expiry,
    )
    db.add(doc)

    # Auto-complete the matching onboarding step
    step_map = {
        DocumentType.DRIVERS_LICENSE: OnboardingStepName.DRIVERS_LICENSE,
        DocumentType.LICENSE_ABSTRACT: OnboardingStepName.LICENSE_ABSTRACT,
        DocumentType.SGI_INSURANCE: OnboardingStepName.SGI_INSURANCE,
        DocumentType.TAXI_LICENSE: OnboardingStepName.TAXI_LICENSE,
        DocumentType.CRIMINAL_CHECK: OnboardingStepName.CRIMINAL_CHECK,
        DocumentType.VEHICLE_INSPECTION: OnboardingStepName.VEHICLE_INSPECTION,
    }
    if doc_type in step_map:
        try:
            await complete_step(
                driver,
                step_map[doc_type],
                db,
                notes=f"Document uploaded: {file.filename}",
                data={"storage_path": storage_path},
            )
        except ValueError:
            pass  # Step may already be complete

    await db.commit()
    completion = await calculate_completion(driver_id, db)
    return {
        "document_id": doc.id,
        "filename": file.filename,
        "doc_type": doc_type.value,
        "storage_path": storage_path,
        "onboarding_completion": round(completion * 100, 1),
    }


@router.get("/{driver_id}/documents")
async def list_documents(driver_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(DriverDocument).where(DriverDocument.driver_id == driver_id)
    )
    docs = result.scalars().all()
    return [
        {
            "id": d.id,
            "doc_type": d.doc_type.value,
            "filename": d.filename,
            "verified": d.verified,
            "expiry_date": d.expiry_date,
            "uploaded_at": d.uploaded_at,
        }
        for d in docs
    ]


@router.post("/{driver_id}/documents/{doc_id}/verify")
async def verify_document(
    driver_id: int,
    doc_id: int,
    verified_by: str = "admin",
    db: AsyncSession = Depends(get_db),
):
    """Mark a document as verified."""
    result = await db.execute(
        select(DriverDocument).where(
            DriverDocument.id == doc_id,
            DriverDocument.driver_id == driver_id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(404, "Document not found")
    doc.verified = True
    doc.verified_by = verified_by
    await db.commit()
    return {"success": True, "document_id": doc_id}
