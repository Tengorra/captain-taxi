"""
Customer record CRUD operations.
"""

from __future__ import annotations
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Customer, Booking, Complaint, ComplaintSeverity, ComplaintStatus, Channel
from services.discount import generate_discount_code


async def get_or_create_customer(
    db: AsyncSession,
    phone: str,
    name: str | None = None,
    email: str | None = None,
) -> Customer:
    """Return existing customer or create a new record."""
    result = await db.execute(select(Customer).where(Customer.phone == phone))
    customer = result.scalar_one_or_none()
    if customer is None:
        customer = Customer(phone=phone, name=name, email=email)
        db.add(customer)
        await db.flush()
    else:
        if name and not customer.name:
            customer.name = name
        if email and not customer.email:
            customer.email = email
    return customer


async def save_booking(
    db: AsyncSession,
    customer: Customer,
    channel: Channel,
    pickup: str,
    dropoff: str,
    trip_id: str | None = None,
    fare_estimate: float | None = None,
    pickup_time: datetime | None = None,
    num_passengers: int = 1,
    notes: str | None = None,
    dispatch_ref: dict | None = None,
) -> Booking:
    booking = Booking(
        trip_id=trip_id or f"CS-{uuid.uuid4().hex[:8].upper()}",
        customer_id=customer.id,
        channel=channel,
        pickup_address=pickup,
        dropoff_address=dropoff,
        pickup_time=pickup_time,
        num_passengers=num_passengers,
        notes=notes,
        fare_estimate=fare_estimate,
        dispatch_ref=dispatch_ref,
    )
    db.add(booking)
    await db.flush()
    return booking


async def log_complaint(
    db: AsyncSession,
    customer: Customer,
    channel: Channel,
    description: str,
    severity: ComplaintSeverity,
    trip_id: str | None = None,
) -> Complaint:
    complaint = Complaint(
        customer_id=customer.id,
        trip_id=trip_id,
        channel=channel,
        description=description,
        severity=severity,
    )

    if severity == ComplaintSeverity.MINOR:
        complaint.discount_code = generate_discount_code()
        complaint.status = ComplaintStatus.RESOLVED
        complaint.resolution_notes = "Auto-resolved: apology + discount sent"

    db.add(complaint)

    # Flag customer if they have 3+ complaints
    result = await db.execute(
        select(Complaint).where(Complaint.customer_id == customer.id)
    )
    existing = result.scalars().all()
    if len(existing) >= 2:  # This new one will be the 3rd
        customer.is_flagged = True
        customer.flag_reason = f"3+ complaints — latest: {description[:80]}"

    await db.flush()
    return complaint


async def get_recent_bookings(
    db: AsyncSession,
    customer: Customer,
    limit: int = 5,
) -> list[Booking]:
    result = await db.execute(
        select(Booking)
        .where(Booking.customer_id == customer.id)
        .order_by(Booking.created_at.desc())
        .limit(limit)
    )
    return result.scalars().all()
