"""
Core Claude conversation loop for the Customer Service Agent.

Handles multi-turn conversations across SMS, WhatsApp, and web chat.
Processes tool calls from Claude and executes the real actions.
"""

from __future__ import annotations
import logging
from datetime import datetime

import anthropic
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from ai.system_prompt import SYSTEM_PROMPT
from ai.tools import TOOLS
from db.customers import (
    get_or_create_customer, save_booking, log_complaint, get_recent_bookings
)
from db.models import Channel, ComplaintSeverity
from services import dispatch as dispatch_svc
from services.notify import (
    send_booking_confirmation, send_discount, alert_owner_escalation
)

logger = logging.getLogger(__name__)
settings = get_settings()

_client: anthropic.AsyncAnthropic | None = None


def _anthropic() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _client


# ── Tool execution ─────────────────────────────────────────────────────────────

async def _execute_tool(
    tool_name: str,
    tool_input: dict,
    db: AsyncSession,
    channel: Channel,
    caller_phone: str | None,  # The phone number of the person we're talking to
) -> str:
    """Execute a tool call from Claude and return a string result."""

    if tool_name == "create_booking":
        phone = tool_input.get("customer_phone") or caller_phone
        name  = tool_input.get("customer_name")
        try:
            customer = await get_or_create_customer(db, phone=phone, name=name)

            # Send to Dispatch Agent
            pickup_time_raw = tool_input.get("pickup_time", "ASAP")
            pickup_dt = None
            if pickup_time_raw and pickup_time_raw != "ASAP":
                try:
                    pickup_dt = datetime.fromisoformat(pickup_time_raw)
                except ValueError:
                    pass

            try:
                dispatch_resp = await dispatch_svc.create_trip(
                    customer_phone=phone,
                    customer_name=name,
                    pickup_address=tool_input["pickup_address"],
                    dropoff_address=tool_input["dropoff_address"],
                    city=tool_input.get("city"),
                    notes=tool_input.get("notes"),
                    scheduled_for=pickup_dt,
                )
                trip_id = dispatch_resp.get("trip_id", f"CS-TEMP-{phone[-4:]}")
            except dispatch_svc.DispatchError as e:
                logger.warning("Dispatch failed, creating local booking: %s", e)
                dispatch_resp = None
                trip_id = None

            booking = await save_booking(
                db,
                customer=customer,
                channel=channel,
                pickup=tool_input["pickup_address"],
                dropoff=tool_input["dropoff_address"],
                trip_id=trip_id,
                pickup_time=pickup_dt,
                num_passengers=tool_input.get("num_passengers", 1),
                notes=tool_input.get("notes"),
                dispatch_ref=dispatch_resp,
            )

            # Send SMS/WhatsApp confirmation
            if caller_phone and channel in (Channel.SMS, Channel.WHATSAPP):
                try:
                    send_booking_confirmation(
                        to_phone=caller_phone,
                        trip_id=booking.trip_id,
                        pickup=tool_input["pickup_address"],
                        dropoff=tool_input["dropoff_address"],
                        channel=channel.value,
                    )
                except Exception as e:
                    logger.warning("Could not send booking confirmation SMS: %s", e)

            return (
                f"Booking confirmed. Trip ID: {booking.trip_id}. "
                f"Pickup: {tool_input['pickup_address']}. "
                f"Dropoff: {tool_input['dropoff_address']}. "
                + ("A driver is being assigned — typical wait 5–15 min." if pickup_dt is None
                   else f"Scheduled for {pickup_dt.strftime('%B %d at %I:%M %p')}.")
            )
        except Exception as e:
            logger.exception("create_booking failed")
            return f"Booking could not be created at this time. Error: {e}"

    elif tool_name == "get_trip_status":
        try:
            status = await dispatch_svc.get_trip_status(tool_input["trip_id"])
            driver = status.get("driver_name", "a driver")
            eta    = status.get("eta_minutes")
            st     = status.get("status", "unknown")
            if eta:
                return f"Trip {tool_input['trip_id']}: status is '{st}'. {driver} is {eta} minutes away."
            return f"Trip {tool_input['trip_id']}: status is '{st}'. No ETA available yet."
        except dispatch_svc.DispatchError:
            return f"I couldn't find trip {tool_input['trip_id']}. Please double-check the trip ID."

    elif tool_name == "cancel_trip":
        try:
            await dispatch_svc.cancel_trip(tool_input["trip_id"], reason=tool_input.get("reason", "Customer request"))
            return f"Trip {tool_input['trip_id']} has been cancelled successfully."
        except dispatch_svc.DispatchError as e:
            return f"Could not cancel trip {tool_input['trip_id']}: {e}"

    elif tool_name == "get_fare_estimate":
        # Simple heuristic — real implementation would use geocoding/routing
        pickup  = tool_input["pickup_address"].lower()
        dropoff = tool_input["dropoff_address"].lower()
        after   = tool_input.get("after_hours", False)

        keywords_airport = ["airport", "yxe", "yqr"]
        is_airport = any(k in pickup or k in dropoff for k in keywords_airport)

        if is_airport:
            estimate = "approximately $25–35"
        elif "warman" in dropoff or "martensville" in dropoff:
            estimate = "approximately $40–55"
        elif "white city" in dropoff or "emerald park" in dropoff:
            estimate = "approximately $25–35"
        else:
            estimate = "approximately $12–25 depending on exact distance"

        surcharge = " Plus the $3 after-hours surcharge applies." if after else ""
        return f"Fare estimate: {estimate}.{surcharge} Minimum fare is $10."

    elif tool_name == "log_complaint":
        try:
            phone = caller_phone or "unknown"
            customer = await get_or_create_customer(db, phone=phone)
            severity = (
                ComplaintSeverity.SERIOUS
                if tool_input["severity"] == "serious"
                else ComplaintSeverity.MINOR
            )
            complaint = await log_complaint(
                db,
                customer=customer,
                channel=channel,
                description=tool_input["description"],
                severity=severity,
                trip_id=tool_input.get("trip_id"),
            )

            if severity == ComplaintSeverity.SERIOUS:
                try:
                    alert_owner_escalation(
                        customer_phone=phone,
                        complaint_description=tool_input["description"],
                        trip_id=tool_input.get("trip_id"),
                        channel=channel.value,
                    )
                except Exception as e:
                    logger.error("Owner alert failed: %s", e)
                return (
                    "I sincerely apologize for this serious incident. "
                    "Our manager has been alerted and will contact you within one hour. "
                    f"Your complaint reference is #{str(complaint.id)[:8].upper()}."
                )
            else:
                # Minor — send discount
                if caller_phone and channel in (Channel.SMS, Channel.WHATSAPP):
                    try:
                        send_discount(caller_phone, complaint.discount_code, channel.value)
                    except Exception as e:
                        logger.warning("Could not send discount SMS: %s", e)
                return (
                    f"I've logged your complaint and I'm truly sorry for the experience. "
                    f"As an apology, a $5 discount code ({complaint.discount_code}) has been sent to you. "
                    f"Reference #{str(complaint.id)[:8].upper()}."
                )
        except Exception as e:
            logger.exception("log_complaint failed")
            return f"Complaint logged (local). Error contacting server: {e}"

    elif tool_name == "lookup_customer_bookings":
        try:
            phone    = tool_input.get("customer_phone") or caller_phone
            customer = await get_or_create_customer(db, phone=phone)
            bookings = await get_recent_bookings(db, customer, limit=5)
            if not bookings:
                return "No recent bookings found for that number."
            lines = []
            for b in bookings:
                ts = b.created_at.strftime("%b %d") if b.created_at else "unknown date"
                lines.append(f"• {b.trip_id}: {b.pickup_address} → {b.dropoff_address} ({ts}, {b.status.value})")
            return "Recent bookings:\n" + "\n".join(lines)
        except Exception as e:
            return f"Could not look up bookings: {e}"

    return f"Unknown tool: {tool_name}"


# ── Main conversation loop ─────────────────────────────────────────────────────

async def run_conversation(
    messages: list[dict],
    db: AsyncSession,
    channel: Channel,
    caller_phone: str | None = None,
) -> tuple[str, list[dict]]:
    """
    Run one turn of the conversation with Claude.

    Args:
        messages:     Full message history (will be extended in-place).
        db:           Active database session.
        channel:      Which channel this conversation is on.
        caller_phone: The customer's phone number (for tool calls + confirmations).

    Returns:
        (reply_text, updated_messages)
    """
    client = _anthropic()
    updated = list(messages)

    # Agentic loop — Claude may call tools multiple times
    while True:
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=updated,
        )

        # Collect text from response
        text_parts   = []
        tool_uses    = []
        tool_results = []

        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_uses.append(block)

        # Add assistant turn to history
        updated.append({"role": "assistant", "content": response.content})

        if not tool_uses:
            # No tools — we have a final text response
            return "\n".join(text_parts).strip(), updated

        # Execute each tool
        for tu in tool_uses:
            try:
                result_text = await _execute_tool(
                    tool_name=tu.name,
                    tool_input=tu.input,
                    db=db,
                    channel=channel,
                    caller_phone=caller_phone,
                )
            except Exception as e:
                logger.exception("Tool %s raised exception", tu.name)
                result_text = f"Tool error: {e}"

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tu.id,
                "content": result_text,
            })

        updated.append({"role": "user", "content": tool_results})

        # Loop back to get Claude's final response after tool results
