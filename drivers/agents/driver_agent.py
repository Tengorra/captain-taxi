"""
Driver Management Agent — Claude-powered orchestrator.

This is the top-level AI agent for driver management. It:
- Accepts natural-language tasks from the Orchestrator Agent
- Uses tool calls to delegate to sub-agents and services
- Handles suspension and termination workflows
- Generates termination letters
"""
import json
import logging
from datetime import datetime
from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import anthropic

from models.driver import Driver, DriverStatus, City
from models.suspension import DriverSuspension, DriverTermination, SuspensionReason, TerminationReason
from agents.onboarding_agent import activate_driver
from agents.communication_agent import send_direct_sms, broadcast_sms
from services.email import send_email
from config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tool definitions for Claude's tool_use
# ---------------------------------------------------------------------------
TOOLS = [
    {
        "name": "get_driver",
        "description": "Look up a driver by ID, name, or phone number.",
        "input_schema": {
            "type": "object",
            "properties": {
                "driver_id": {"type": "integer"},
                "name": {"type": "string"},
                "phone": {"type": "string"},
            },
        },
    },
    {
        "name": "suspend_driver",
        "description": "Suspend a driver immediately (locks them out). Provide reason and detail.",
        "input_schema": {
            "type": "object",
            "required": ["driver_id", "reason"],
            "properties": {
                "driver_id": {"type": "integer"},
                "reason": {
                    "type": "string",
                    "enum": [r.value for r in SuspensionReason],
                },
                "detail": {"type": "string"},
            },
        },
    },
    {
        "name": "lift_suspension",
        "description": "Lift an active suspension for a driver.",
        "input_schema": {
            "type": "object",
            "required": ["driver_id"],
            "properties": {
                "driver_id": {"type": "integer"},
                "reason": {"type": "string"},
            },
        },
    },
    {
        "name": "request_termination",
        "description": (
            "Request termination of a driver. ALWAYS requires owner approval — "
            "this only initiates the process and notifies the owner."
        ),
        "input_schema": {
            "type": "object",
            "required": ["driver_id", "reason"],
            "properties": {
                "driver_id": {"type": "integer"},
                "reason": {
                    "type": "string",
                    "enum": [r.value for r in TerminationReason],
                },
                "detail": {"type": "string"},
            },
        },
    },
    {
        "name": "activate_driver",
        "description": "Activate a driver who has completed all onboarding steps.",
        "input_schema": {
            "type": "object",
            "required": ["driver_id"],
            "properties": {
                "driver_id": {"type": "integer"},
            },
        },
    },
    {
        "name": "send_message",
        "description": "Send an SMS message to a specific driver or broadcast to all/city.",
        "input_schema": {
            "type": "object",
            "required": ["message"],
            "properties": {
                "driver_id": {"type": "integer", "description": "Omit for broadcast"},
                "city": {
                    "type": "string",
                    "enum": ["saskatoon", "regina"],
                    "description": "For city-wide broadcast; omit for all drivers",
                },
                "message": {"type": "string"},
            },
        },
    },
    {
        "name": "list_drivers",
        "description": "List drivers filtered by status and/or city.",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": [s.value for s in DriverStatus],
                },
                "city": {"type": "string", "enum": ["saskatoon", "regina"]},
            },
        },
    },
]


# ---------------------------------------------------------------------------
# Tool execution
# ---------------------------------------------------------------------------

async def _execute_tool(name: str, inputs: dict, db: AsyncSession) -> Any:
    if name == "get_driver":
        return await _tool_get_driver(inputs, db)
    if name == "suspend_driver":
        return await _tool_suspend_driver(inputs, db)
    if name == "lift_suspension":
        return await _tool_lift_suspension(inputs, db)
    if name == "request_termination":
        return await _tool_request_termination(inputs, db)
    if name == "activate_driver":
        return await _tool_activate_driver(inputs, db)
    if name == "send_message":
        return await _tool_send_message(inputs, db)
    if name == "list_drivers":
        return await _tool_list_drivers(inputs, db)
    return {"error": f"Unknown tool: {name}"}


async def _tool_get_driver(inputs: dict, db: AsyncSession) -> dict:
    query = select(Driver)
    if "driver_id" in inputs:
        query = query.where(Driver.id == inputs["driver_id"])
    elif "phone" in inputs:
        query = query.where(Driver.phone == inputs["phone"])
    elif "name" in inputs:
        name = inputs["name"].strip()
        parts = name.split()
        if len(parts) >= 2:
            query = query.where(
                Driver.first_name.ilike(f"%{parts[0]}%"),
                Driver.last_name.ilike(f"%{parts[-1]}%"),
            )
        else:
            query = query.where(
                Driver.first_name.ilike(f"%{name}%") |
                Driver.last_name.ilike(f"%{name}%")
            )
    result = await db.execute(query.limit(5))
    drivers = result.scalars().all()
    return [_driver_summary(d) for d in drivers]


async def _tool_suspend_driver(inputs: dict, db: AsyncSession) -> dict:
    driver = await _get_driver_by_id(inputs["driver_id"], db)
    if not driver:
        return {"error": "Driver not found"}
    if driver.status == DriverStatus.TERMINATED:
        return {"error": "Cannot suspend a terminated driver"}

    prev_status = driver.status
    driver.status = DriverStatus.SUSPENDED
    suspension = DriverSuspension(
        driver_id=driver.id,
        reason=SuspensionReason(inputs["reason"]),
        detail=inputs.get("detail"),
        suspended_by="agent",
    )
    db.add(suspension)
    await db.commit()

    await send_direct_sms(
        driver,
        f"Hi {driver.first_name}, your Captain Taxi account has been suspended. "
        "Please contact dispatch for more information.",
        db,
    )
    logger.info(f"Driver {driver.id} suspended (was {prev_status})")
    return {"success": True, "driver": driver.full_name, "suspension_id": suspension.id}


async def _tool_lift_suspension(inputs: dict, db: AsyncSession) -> dict:
    driver = await _get_driver_by_id(inputs["driver_id"], db)
    if not driver:
        return {"error": "Driver not found"}
    if driver.status != DriverStatus.SUSPENDED:
        return {"error": "Driver is not suspended"}

    # Find active suspension
    result = await db.execute(
        select(DriverSuspension)
        .where(
            DriverSuspension.driver_id == driver.id,
            DriverSuspension.lifted_at.is_(None),
        )
        .order_by(DriverSuspension.created_at.desc())
        .limit(1)
    )
    suspension = result.scalar_one_or_none()
    if suspension:
        suspension.lifted_at = datetime.utcnow()
        suspension.lifted_by = "agent"

    driver.status = DriverStatus.ACTIVE
    await db.commit()

    await send_direct_sms(
        driver,
        f"Hi {driver.first_name}, your Captain Taxi suspension has been lifted. "
        "Your account is now active. Drive safe!",
        db,
    )
    return {"success": True, "driver": driver.full_name}


async def _tool_request_termination(inputs: dict, db: AsyncSession) -> dict:
    driver = await _get_driver_by_id(inputs["driver_id"], db)
    if not driver:
        return {"error": "Driver not found"}

    # Check if termination already requested
    existing = await db.execute(
        select(DriverTermination).where(DriverTermination.driver_id == driver.id)
    )
    if existing.scalar_one_or_none():
        return {"error": "Termination already requested for this driver"}

    reason = TerminationReason(inputs["reason"])
    detail = inputs.get("detail", "")

    # Generate termination letter
    letter = await _generate_termination_letter(driver, reason, detail)

    termination = DriverTermination(
        driver_id=driver.id,
        reason=reason,
        detail=detail,
        termination_letter=letter,
        owner_approved=False,
    )
    db.add(termination)

    # Suspend immediately pending owner decision
    if driver.status == DriverStatus.ACTIVE:
        driver.status = DriverStatus.SUSPENDED
        suspension = DriverSuspension(
            driver_id=driver.id,
            reason=SuspensionReason.INVESTIGATION,
            detail="Pending termination review by owner",
            suspended_by="agent",
        )
        db.add(suspension)

    await db.commit()

    # Notify owner — MUST approve before termination is final
    approval_url = f"{settings.base_url}/admin/drivers/{driver.id}/termination/{termination.id}/approve"
    await send_email(
        to=settings.owner_email,
        subject=f"ACTION REQUIRED: Termination Request — {driver.full_name}",
        html_body=f"""
        <div style="font-family:Arial,sans-serif;max-width:600px">
          <h2 style="color:#e63946">Driver Termination Request</h2>
          <p>The Driver Management Agent has flagged <strong>{driver.full_name}</strong>
             for termination and is awaiting your approval.</p>
          <p><strong>Reason:</strong> {reason.value}</p>
          <p><strong>Detail:</strong> {detail}</p>
          <h3>Draft Termination Letter</h3>
          <div style="background:#f4f4f4;padding:16px;border-radius:6px;
                      white-space:pre-wrap;font-size:14px">{letter}</div>
          <br>
          <a href="{approval_url}"
             style="background:#e63946;color:#fff;padding:12px 24px;
                    border-radius:4px;text-decoration:none;display:inline-block">
            Approve Termination
          </a>
          &nbsp;
          <a href="{settings.base_url}/admin/drivers/{driver.id}"
             style="background:#666;color:#fff;padding:12px 24px;
                    border-radius:4px;text-decoration:none;display:inline-block">
            View Driver Profile
          </a>
        </div>
        """,
    )
    await send_sms(
        settings.owner_phone,
        f"Captain Taxi: Termination request for {driver.full_name}. "
        f"Your approval required. Check email or: {approval_url}"
    )

    logger.info(f"Termination requested for driver {driver.id} — awaiting owner approval")
    return {
        "success": True,
        "driver": driver.full_name,
        "termination_id": termination.id,
        "status": "pending_owner_approval",
    }


async def _tool_activate_driver(inputs: dict, db: AsyncSession) -> dict:
    driver = await _get_driver_by_id(inputs["driver_id"], db)
    if not driver:
        return {"error": "Driver not found"}
    try:
        await activate_driver(driver, db)
        return {"success": True, "driver": driver.full_name}
    except ValueError as e:
        return {"error": str(e)}


async def _tool_send_message(inputs: dict, db: AsyncSession) -> dict:
    body = inputs["message"]

    if "driver_id" in inputs:
        driver = await _get_driver_by_id(inputs["driver_id"], db)
        if not driver:
            return {"error": "Driver not found"}
        await send_direct_sms(driver, body, db)
        return {"success": True, "recipient": driver.full_name}

    city = City(inputs["city"]) if "city" in inputs else None
    broadcast = await broadcast_sms(body, db, city=city, sent_by="agent")
    return {"success": True, "broadcast_id": broadcast.id}


async def _tool_list_drivers(inputs: dict, db: AsyncSession) -> list[dict]:
    query = select(Driver)
    if "status" in inputs:
        query = query.where(Driver.status == DriverStatus(inputs["status"]))
    if "city" in inputs:
        query = query.where(Driver.city == City(inputs["city"]))
    result = await db.execute(query.limit(50))
    return [_driver_summary(d) for d in result.scalars().all()]


# ---------------------------------------------------------------------------
# Main agent entry point
# ---------------------------------------------------------------------------

async def run_driver_agent(task: str, db: AsyncSession) -> str:
    """
    Run the Driver Management Agent with a natural-language task.
    Uses Claude with tool_use in an agentic loop.
    Returns the final answer/summary.
    """
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    messages = [{"role": "user", "content": task}]

    system = f"""You are the Driver Management Agent for Captain Taxi,
a taxi company in Saskatoon and Regina, Saskatchewan, Canada.

You manage 31–60 drivers across both cities. You have tools to:
- Look up, list, and manage drivers
- Suspend or reactivate drivers
- Request terminations (ALWAYS requires owner approval — never terminate unilaterally)
- Send messages to individual drivers or broadcast to all/city
- Activate newly onboarded drivers

Rules:
1. Terminations MUST be escalated to the owner ({settings.owner_name}) — never final without approval.
2. Suspensions can be done autonomously for clear policy violations.
3. Be concise and action-oriented.
4. When in doubt, notify the owner rather than acting autonomously.
Today's date: {datetime.utcnow().strftime('%Y-%m-%d')}
"""

    for _ in range(10):  # max 10 tool iterations
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=system,
            tools=TOOLS,
            messages=messages,
        )

        if response.stop_reason == "end_turn":
            return _extract_text(response)

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = await _execute_tool(block.name, block.input, db)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result),
                    })
            messages.append({"role": "user", "content": tool_results})
        else:
            break

    return _extract_text(response)


def _extract_text(response) -> str:
    for block in response.content:
        if hasattr(block, "text"):
            return block.text
    return "Task completed."


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_driver_by_id(driver_id: int, db: AsyncSession) -> Driver | None:
    result = await db.execute(select(Driver).where(Driver.id == driver_id))
    return result.scalar_one_or_none()


def _driver_summary(driver: Driver) -> dict:
    return {
        "id": driver.id,
        "name": driver.full_name,
        "phone": driver.phone,
        "email": driver.email,
        "city": driver.city.value,
        "status": driver.status.value,
        "onboarding_completion": f"{driver.onboarding_completion:.0%}",
        "is_available": driver.is_available,
    }


async def _generate_termination_letter(
    driver: Driver,
    reason: TerminationReason,
    detail: str,
) -> str:
    """Use Claude to generate a professional termination letter."""
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    prompt = f"""Write a professional employment termination letter for:
Driver: {driver.full_name}
Company: Captain Taxi (Saskatoon/Regina, Saskatchewan)
Reason: {reason.value}
Detail: {detail}
Date: {datetime.utcnow().strftime('%B %d, %Y')}

The letter should be professional, factual, and compliant with Saskatchewan employment standards.
Include: effective date (today), reason, final pay notice, return of company property (if any).
Do not include placeholders — write the complete letter ready to send.
"""
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


async def approve_termination(termination_id: int, db: AsyncSession) -> dict:
    """
    Owner has approved the termination — finalize it.
    This is called from the admin endpoint.
    """
    result = await db.execute(
        select(DriverTermination).where(DriverTermination.id == termination_id)
    )
    termination = result.scalar_one_or_none()
    if not termination:
        return {"error": "Termination record not found"}
    if termination.owner_approved:
        return {"error": "Already approved"}

    termination.owner_approved = True
    termination.owner_approved_at = datetime.utcnow()
    termination.effective_at = datetime.utcnow()

    # Get driver and finalize
    driver = await _get_driver_by_id(termination.driver_id, db)
    if driver:
        driver.status = DriverStatus.TERMINATED
        await db.commit()

        # Send termination letter to driver via email
        await send_email(
            to=driver.email,
            subject="Captain Taxi — Notice of Termination",
            html_body=f"<div style='font-family:Arial;max-width:600px'>"
                      f"<pre style='white-space:pre-wrap'>{termination.termination_letter}</pre>"
                      f"</div>",
            text_body=termination.termination_letter,
        )
        # Final SMS
        await send_direct_sms(
            driver,
            f"Hi {driver.first_name}, your employment with Captain Taxi has been terminated "
            "effective today. A formal letter has been sent to your email.",
            db,
        )

    logger.info(f"Termination approved and finalized for driver {termination.driver_id}")
    return {"success": True, "driver": driver.full_name if driver else "unknown"}
