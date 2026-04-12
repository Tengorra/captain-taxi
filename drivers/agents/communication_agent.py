"""
Communication Agent.

Responsibilities:
- Send broadcast announcements (all drivers or by city)
- Direct message individual driver via SMS/email
- Parse inbound SMS commands from drivers and respond automatically
- Escalate messages the agent can't handle to the owner
"""
import logging
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import anthropic

from models.driver import Driver, DriverStatus, City
from models.communication import (
    Message, Broadcast, BroadcastRecipient,
    MessageDirection, MessageChannel, MessageStatus
)
from services.sms import send_sms
from services.email import send_email
from config import settings

logger = logging.getLogger(__name__)

# SMS self-service commands
SMS_COMMANDS = {
    "AVAILABLE", "OFFLINE", "SCHEDULE", "EARNINGS", "HELP"
}


async def send_direct_sms(
    driver: Driver,
    body: str,
    db: AsyncSession,
) -> Message:
    """Send an SMS to a specific driver and log it."""
    sid = await send_sms(driver.phone, body)
    msg = Message(
        driver_id=driver.id,
        direction=MessageDirection.OUTBOUND,
        channel=MessageChannel.SMS,
        body=body,
        status=MessageStatus.SENT if sid else MessageStatus.FAILED,
        twilio_sid=sid,
        sent_at=datetime.utcnow() if sid else None,
    )
    db.add(msg)
    await db.commit()
    return msg


async def send_direct_email(
    driver: Driver,
    subject: str,
    body_html: str,
    db: AsyncSession,
) -> Message:
    """Send an email to a specific driver and log it."""
    ok = await send_email(driver.email, subject, body_html)
    msg = Message(
        driver_id=driver.id,
        direction=MessageDirection.OUTBOUND,
        channel=MessageChannel.EMAIL,
        subject=subject,
        body=body_html,
        status=MessageStatus.SENT if ok else MessageStatus.FAILED,
        sent_at=datetime.utcnow() if ok else None,
    )
    db.add(msg)
    await db.commit()
    return msg


async def broadcast_sms(
    body: str,
    db: AsyncSession,
    city: City | None = None,
    sent_by: str = "agent",
) -> Broadcast:
    """Send SMS to all active drivers, optionally filtered by city."""
    query = select(Driver).where(Driver.status == DriverStatus.ACTIVE)
    if city:
        query = query.where(Driver.city == city)
    result = await db.execute(query)
    drivers = list(result.scalars().all())

    broadcast = Broadcast(
        body=body,
        channel=MessageChannel.SMS,
        city_filter=city,
        sent_by=sent_by,
    )
    db.add(broadcast)
    await db.flush()

    for driver in drivers:
        sid = await send_sms(driver.phone, body)
        recipient = BroadcastRecipient(
            broadcast_id=broadcast.id,
            driver_id=driver.id,
            status=MessageStatus.SENT if sid else MessageStatus.FAILED,
            twilio_sid=sid,
            sent_at=datetime.utcnow() if sid else None,
        )
        db.add(recipient)

    await db.commit()
    logger.info(
        f"Broadcast SMS sent to {len(drivers)} drivers "
        f"(city={city.value if city else 'all'})"
    )
    return broadcast


# ---------------------------------------------------------------------------
# Inbound SMS handler
# ---------------------------------------------------------------------------

async def handle_inbound_sms(
    from_phone: str,
    body: str,
    db: AsyncSession,
) -> str:
    """
    Process an inbound SMS from a driver.
    Returns the reply text (already sent to driver).
    """
    # Look up driver by phone
    result = await db.execute(
        select(Driver).where(Driver.phone == from_phone)
    )
    driver = result.scalar_one_or_none()

    if not driver:
        reply = (
            "Hello! We don't recognize this number. "
            "If you're a Captain Taxi driver, please contact dispatch."
        )
        await send_sms(from_phone, reply)
        return reply

    # Log inbound message
    inbound = Message(
        driver_id=driver.id,
        direction=MessageDirection.INBOUND,
        channel=MessageChannel.SMS,
        body=body,
        status=MessageStatus.DELIVERED,
    )
    db.add(inbound)
    await db.flush()

    cmd = body.strip().upper()

    if cmd in SMS_COMMANDS:
        reply = await _handle_command(driver, cmd, db)
    else:
        # Unknown message — use Claude to respond or escalate
        reply = await _ai_respond(driver, body, db)

    # Log outbound reply
    sid = await send_sms(driver.phone, reply)
    outbound = Message(
        driver_id=driver.id,
        direction=MessageDirection.OUTBOUND,
        channel=MessageChannel.SMS,
        body=reply,
        status=MessageStatus.SENT if sid else MessageStatus.FAILED,
        twilio_sid=sid,
        sent_at=datetime.utcnow(),
        agent_response=reply,
    )
    db.add(outbound)
    inbound.agent_response = reply
    await db.commit()
    return reply


async def _handle_command(driver: Driver, cmd: str, db: AsyncSession) -> str:
    """Handle a known SMS self-service command."""
    if cmd == "HELP":
        return (
            f"Hi {driver.first_name}! Captain Taxi commands:\n"
            "AVAILABLE — mark yourself available\n"
            "OFFLINE — mark yourself offline\n"
            "SCHEDULE — get this week's schedule\n"
            "EARNINGS — get this week's earnings\n"
            "HELP — show this message"
        )

    if cmd == "AVAILABLE":
        if driver.status != DriverStatus.ACTIVE:
            return "Your account is not active. Contact dispatch."
        driver.is_available = True
        await db.commit()
        return f"Got it, {driver.first_name}! You're marked AVAILABLE. Drive safe!"

    if cmd == "OFFLINE":
        driver.is_available = False
        await db.commit()
        return f"You're now OFFLINE, {driver.first_name}. See you next time!"

    if cmd == "SCHEDULE":
        from datetime import date, timedelta
        from models.schedule import ShiftAssignment, Shift
        from sqlalchemy import and_

        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        result = await db.execute(
            select(ShiftAssignment, Shift)
            .join(Shift, ShiftAssignment.shift_id == Shift.id)
            .where(
                and_(
                    ShiftAssignment.driver_id == driver.id,
                    Shift.shift_date >= week_start,
                    Shift.shift_date < week_start + timedelta(days=7),
                )
            )
            .order_by(Shift.shift_date, Shift.time_block)
        )
        rows = result.all()
        if not rows:
            return f"Hi {driver.first_name}, you have no shifts this week."
        lines = [f"{shift.shift_date.strftime('%a %b %d')}: {shift.time_block.value}" for _, shift in rows]
        return f"Your schedule this week:\n" + "\n".join(lines)

    if cmd == "EARNINGS":
        from datetime import date, timedelta
        from sqlalchemy import and_

        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        from models.performance import DriverMetrics
        result = await db.execute(
            select(DriverMetrics).where(
                and_(
                    DriverMetrics.driver_id == driver.id,
                    DriverMetrics.week_start == week_start,
                )
            )
        )
        metrics = result.scalar_one_or_none()
        if not metrics:
            return f"Hi {driver.first_name}, no earnings data yet for this week."
        return (
            f"Hi {driver.first_name}! Week of {week_start}: "
            f"{metrics.trips_completed} trips, "
            f"${metrics.income_earned:.2f} earned, "
            f"{metrics.hours_online:.1f} hrs online."
        )

    return "Unknown command. Reply HELP for options."


async def _ai_respond(driver: Driver, body: str, db: AsyncSession) -> str:
    """
    Use Claude to handle an unrecognized inbound message.
    Falls back to escalating to owner if confidence is low.
    """
    # Fetch recent message history for context
    result = await db.execute(
        select(Message)
        .where(Message.driver_id == driver.id)
        .order_by(Message.created_at.desc())
        .limit(10)
    )
    history = list(reversed(result.scalars().all()))

    history_text = "\n".join(
        f"[{m.direction.value.upper()}]: {m.body}" for m in history
    )

    system_prompt = f"""You are the Driver Management Agent for Captain Taxi,
a taxi company in Saskatoon and Regina, Saskatchewan, Canada.

You are responding to an SMS from driver {driver.full_name} (ID: {driver.id},
city: {driver.city.value.title()}, status: {driver.status.value}).

Your role:
- Answer questions about their schedule, earnings, or company policy
- Help with simple requests
- If the message requires human judgment (disputes, disciplinary, pay errors, etc.),
  reply saying you're escalating to the team

Keep replies SHORT (under 160 chars if possible — this is SMS).
Do not make up policy details you don't know.
Recent conversation:
{history_text}
"""

    try:
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=200,
            system=system_prompt,
            messages=[{"role": "user", "content": body}],
        )
        reply = response.content[0].text.strip()

        # Detect escalation keywords
        escalate_triggers = ["escalat", "human", "team will", "contact dispatch", "speak with"]
        if any(t in reply.lower() for t in escalate_triggers):
            await _escalate_to_owner(driver, body, db)

        return reply

    except Exception as e:
        logger.error(f"Claude API error handling inbound SMS: {e}")
        await _escalate_to_owner(driver, body, db)
        return (
            f"Hi {driver.first_name}, I wasn't able to process your message right now. "
            "Our team has been notified and will follow up shortly."
        )


async def _escalate_to_owner(driver: Driver, original_message: str, db: AsyncSession) -> None:
    """Notify the owner of a message the agent couldn't handle."""
    notify = (
        f"Captain Taxi: Driver {driver.full_name} ({driver.phone}) sent a message "
        f"that needs your attention:\n\"{original_message}\""
    )
    await send_sms(settings.owner_phone, notify)
    logger.info(f"Inbound SMS from driver {driver.id} escalated to owner.")
