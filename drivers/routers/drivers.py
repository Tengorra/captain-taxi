"""Driver CRUD + admin actions."""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.driver import Driver, DriverStatus, City
from agents.onboarding_agent import initialize_onboarding, activate_driver
from agents.driver_agent import run_driver_agent, approve_termination

router = APIRouter(prefix="/drivers", tags=["drivers"])


class DriverCreate(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    phone: str  # E.164 e.g. +13061234567
    city: City
    vehicle_make: Optional[str] = None
    vehicle_model: Optional[str] = None
    vehicle_year: Optional[int] = None
    vehicle_plate: Optional[str] = None
    vehicle_color: Optional[str] = None


class DriverResponse(BaseModel):
    id: int
    first_name: str
    last_name: str
    email: str
    phone: str
    city: str
    status: str
    onboarding_completion: float
    is_available: bool
    created_at: datetime

    class Config:
        from_attributes = True


class AgentTaskRequest(BaseModel):
    task: str


@router.post("/", response_model=DriverResponse, status_code=status.HTTP_201_CREATED)
async def register_driver(payload: DriverCreate, db: AsyncSession = Depends(get_db)):
    """Register a new driver and kick off onboarding."""
    # Check for duplicate email/phone
    existing = await db.execute(
        select(Driver).where(
            (Driver.email == payload.email) | (Driver.phone == payload.phone)
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(409, "Driver with this email or phone already exists.")

    driver = Driver(**payload.model_dump())
    db.add(driver)
    await db.flush()
    await initialize_onboarding(driver, db)
    await db.commit()
    await db.refresh(driver)
    return driver


@router.get("/", response_model=list[DriverResponse])
async def list_drivers(
    status: Optional[DriverStatus] = None,
    city: Optional[City] = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Driver)
    if status:
        query = query.where(Driver.status == status)
    if city:
        query = query.where(Driver.city == city)
    result = await db.execute(query.order_by(Driver.created_at.desc()))
    return result.scalars().all()


@router.get("/{driver_id}", response_model=DriverResponse)
async def get_driver(driver_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Driver).where(Driver.id == driver_id))
    driver = result.scalar_one_or_none()
    if not driver:
        raise HTTPException(404, "Driver not found")
    return driver


@router.post("/{driver_id}/activate")
async def activate(driver_id: int, db: AsyncSession = Depends(get_db)):
    """Owner activates a driver who has completed onboarding."""
    result = await db.execute(select(Driver).where(Driver.id == driver_id))
    driver = result.scalar_one_or_none()
    if not driver:
        raise HTTPException(404, "Driver not found")
    try:
        await activate_driver(driver, db)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"success": True, "driver": driver.full_name}


@router.post("/agent/task")
async def agent_task(payload: AgentTaskRequest, db: AsyncSession = Depends(get_db)):
    """
    Send a natural-language task to the Driver Management Agent.
    For use by the Orchestrator Agent or admin UI.
    """
    result = await run_driver_agent(payload.task, db)
    return {"result": result}


@router.post("/terminations/{termination_id}/approve")
async def approve_driver_termination(
    termination_id: int, db: AsyncSession = Depends(get_db)
):
    """Owner approval endpoint for driver termination."""
    result = await approve_termination(termination_id, db)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result
