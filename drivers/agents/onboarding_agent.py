"""
Onboarding state machine.

Responsibilities:
- Initialize onboarding steps for a new driver
- Advance steps when driver submits data/documents
- Calculate completion percentage
- Send step-by-step email + SMS prompts
- Notify owner when a driver reaches 100%
"""
import logging
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.driver import (
    Driver, DriverStatus, OnboardingStep, OnboardingStepName,
    ONBOARDING_STEPS_ORDERED, STEP_LABELS
)
from services.sms import send_sms
from services.email import send_email, onboarding_email_html
from config import settings

logger = logging.getLogger(__name__)

# Human-readable instructions for each step sent to the driver
STEP_INSTRUCTIONS = {
    OnboardingStepName.PERSONAL_INFO: (
        "Please provide your full legal name, home address, and date of birth "
        "by logging into your driver portal."
    ),
    OnboardingStepName.SIN: (
        "Please submit your Social Insurance Number (SIN) securely through the portal. "
        "This is required for payroll and tax reporting."
    ),
    OnboardingStepName.DRIVERS_LICENSE: (
        "Upload a clear photo of both sides of your Saskatchewan driver's licence."
    ),
    OnboardingStepName.LICENSE_ABSTRACT: (
        "Obtain a driver's abstract from SGI (sgi.sk.ca) dated within the last 30 days "
        "and upload it to the portal."
    ),
    OnboardingStepName.SGI_INSURANCE: (
        "Upload your current SGI vehicle insurance certificate showing commercial coverage."
    ),
    OnboardingStepName.TAXI_LICENSE: (
        "Upload your City of Saskatoon or City of Regina taxi/chauffeur permit."
    ),
    OnboardingStepName.CRIMINAL_CHECK: (
        "Submit a criminal record check from your local police service or an accredited "
        "online provider, dated within the last 90 days."
    ),
    OnboardingStepName.VEHICLE_INSPECTION: (
        "Book a vehicle inspection at an approved facility and upload the signed inspection report."
    ),
    OnboardingStepName.BANK_INFO: (
        "Provide your bank details for direct deposit: institution name, transit number, "
        "and account number via the secure portal."
    ),
}


async def initialize_onboarding(driver: Driver, db: AsyncSession) -> None:
    """Create all onboarding step records for a newly registered driver."""
    for step_name in ONBOARDING_STEPS_ORDERED:
        step = OnboardingStep(driver_id=driver.id, step=step_name)
        db.add(step)
    await db.commit()
    logger.info(f"Onboarding initialized for driver {driver.id} ({driver.full_name})")


async def get_steps(driver_id: int, db: AsyncSession) -> list[OnboardingStep]:
    result = await db.execute(
        select(OnboardingStep)
        .where(OnboardingStep.driver_id == driver_id)
        .order_by(OnboardingStep.id)
    )
    return list(result.scalars().all())


async def calculate_completion(driver_id: int, db: AsyncSession) -> float:
    steps = await get_steps(driver_id, db)
    if not steps:
        return 0.0
    completed = sum(1 for s in steps if s.completed)
    return completed / len(steps)


async def complete_step(
    driver: Driver,
    step_name: OnboardingStepName,
    db: AsyncSession,
    notes: str | None = None,
    data: dict | None = None,
) -> OnboardingStep:
    """Mark a step complete and advance the onboarding workflow."""
    result = await db.execute(
        select(OnboardingStep).where(
            OnboardingStep.driver_id == driver.id,
            OnboardingStep.step == step_name,
        )
    )
    step = result.scalar_one_or_none()
    if not step:
        raise ValueError(f"Step {step_name} not found for driver {driver.id}")

    step.completed = True
    step.completed_at = datetime.utcnow()
    if notes:
        step.notes = notes
    if data:
        step.data = data

    completion = await calculate_completion(driver.id, db)
    driver.onboarding_completion = completion
    await db.commit()

    logger.info(
        f"Driver {driver.id}: step '{step_name}' complete. "
        f"Overall: {completion:.0%}"
    )

    if completion >= 1.0:
        await _handle_onboarding_complete(driver, db)
    else:
        await _prompt_next_step(driver, db)

    return step


async def _prompt_next_step(driver: Driver, db: AsyncSession) -> None:
    """Find the next incomplete step and send email + SMS to the driver."""
    steps = await get_steps(driver.id, db)
    next_step = next((s for s in steps if not s.completed), None)
    if not next_step:
        return

    step_label = STEP_LABELS[next_step.step]
    instruction = STEP_INSTRUCTIONS[next_step.step]
    portal_url = f"{settings.base_url}/driver-portal/{driver.id}"
    pct = int(driver.onboarding_completion * 100)

    # SMS — short and actionable
    sms_body = (
        f"Hi {driver.first_name}, Captain Taxi onboarding {pct}% done. "
        f"Next step: {step_label}. {instruction[:100]}... "
        f"Portal: {portal_url}"
    )
    await send_sms(driver.phone, sms_body)

    # Email — detailed
    html = onboarding_email_html(
        driver_name=driver.first_name,
        step_label=step_label,
        detail=instruction,
        portal_url=portal_url,
    )
    await send_email(
        to=driver.email,
        subject=f"Captain Taxi Onboarding — Next Step: {step_label}",
        html_body=html,
        text_body=instruction,
    )
    driver.onboarding_reminder_count += 1
    await db.commit()


async def _handle_onboarding_complete(driver: Driver, db: AsyncSession) -> None:
    """All steps done — notify owner; driver stays ONBOARDING until owner activates."""
    logger.info(f"Driver {driver.id} ({driver.full_name}) completed onboarding. Notifying owner.")

    # SMS to owner
    owner_sms = (
        f"Captain Taxi: {driver.full_name} has completed all onboarding steps "
        f"and is ready to activate. City: {driver.city.value.title()}. "
        f"Review: {settings.base_url}/admin/drivers/{driver.id}"
    )
    await send_sms(settings.owner_phone, owner_sms)

    # Email to owner
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px">
      <h2>New Driver Ready to Activate</h2>
      <p><strong>{driver.full_name}</strong> has completed all onboarding requirements.</p>
      <ul>
        <li>City: {driver.city.value.title()}</li>
        <li>Phone: {driver.phone}</li>
        <li>Email: {driver.email}</li>
      </ul>
      <a href="{settings.base_url}/admin/drivers/{driver.id}"
         style="background:#e63946;color:#fff;padding:10px 20px;border-radius:4px;
                text-decoration:none;display:inline-block">
        Review &amp; Activate Driver
      </a>
    </div>
    """
    await send_email(
        to=settings.owner_email,
        subject=f"Action Required: Activate Driver — {driver.full_name}",
        html_body=html,
    )

    # Confirm to driver
    await send_sms(
        driver.phone,
        f"Hi {driver.first_name}! Your Captain Taxi onboarding is complete. "
        "Our team will review and activate your account shortly. Thank you!"
    )


async def send_onboarding_reminder(driver: Driver, db: AsyncSession) -> None:
    """Re-send a nudge for the current pending step (used by weekly job)."""
    if driver.onboarding_completion >= 1.0:
        return
    await _prompt_next_step(driver, db)


async def activate_driver(driver: Driver, db: AsyncSession) -> None:
    """Owner has approved — set driver to ACTIVE."""
    if driver.onboarding_completion < 1.0:
        raise ValueError("Cannot activate driver with incomplete onboarding.")
    driver.status = DriverStatus.ACTIVE
    driver.activated_at = datetime.utcnow()
    await db.commit()

    await send_sms(
        driver.phone,
        f"Congratulations {driver.first_name}! Your Captain Taxi account is now ACTIVE. "
        "You can start accepting rides. Reply HELP for available commands."
    )
    await send_email(
        to=driver.email,
        subject="Welcome to Captain Taxi — Your Account is Active!",
        html_body=f"""
        <div style="font-family:Arial,sans-serif;max-width:600px">
          <h2>Welcome to Captain Taxi, {driver.first_name}!</h2>
          <p>Your driver account is now <strong>active</strong>. You can begin accepting rides.</p>
          <p>Text <strong>HELP</strong> to {settings.twilio_phone_number} for available SMS commands.</p>
        </div>
        """,
    )
    logger.info(f"Driver {driver.id} ({driver.full_name}) activated.")
