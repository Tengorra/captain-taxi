"""
WhatsApp Command Handler — Processes inbound WhatsApp messages from the owner.
"""
import re
from datetime import datetime, date
from sqlalchemy.orm import Session
from ..db.models import Driver, Trip, Escalation, Alert
from ..db.database import redis_client
from ..services.twilio_service import send_whatsapp
from .admin_agent import answer_owner_query

OWNER_NUMBERS: set = set()

TRIP_COMPLETED = "completed"
ESC_OPEN = "open"
ESC_RESOLVED = "resolved"


def is_authorized(from_number: str) -> bool:
    return from_number in OWNER_NUMBERS


def _get_live_context(db: Session) -> dict:
    try:
        sk_online = int(redis_client.get("drivers:online:saskatoon") or 0)
        reg_online = int(redis_client.get("drivers:online:regina") or 0)
        sk_trips = int(redis_client.get("trips:active:saskatoon") or 0)
        reg_trips = int(redis_client.get("trips:active:regina") or 0)

        today = date.today()
        today_trips = db.query(Trip).filter(
            Trip.status == TRIP_COMPLETED,
            Trip.completed_at >= datetime(today.year, today.month, today.day)
        ).all()
        today_revenue = sum((t.fare or 0) for t in today_trips)

        pending_esc = db.query(Escalation).filter(Escalation.status == ESC_OPEN).count()
        unread_alerts = db.query(Alert).filter_by(is_read=False).count()

        return {
            "drivers_online": {"saskatoon": sk_online, "regina": reg_online, "total": sk_online + reg_online},
            "active_trips": {"saskatoon": sk_trips, "regina": reg_trips},
            "today_revenue": round(today_revenue, 2),
            "today_trip_count": len(today_trips),
            "pending_escalations": pending_esc,
            "unread_alerts": unread_alerts,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        return {"error": str(e), "timestamp": datetime.now().isoformat()}


def _handle_structured_command(command: str, args: str, db: Session):
    cmd = command.lower().strip()

    if cmd in ("drivers online", "how many drivers", "drivers"):
        sk = int(redis_client.get("drivers:online:saskatoon") or 0)
        reg = int(redis_client.get("drivers:online:regina") or 0)
        return f"Drivers online:\n- Saskatoon: {sk}\n- Regina: {reg}\n- Total: {sk + reg}"

    if cmd in ("revenue today", "revenue", "money today"):
        today = date.today()
        trips = db.query(Trip).filter(
            Trip.status == TRIP_COMPLETED,
            Trip.completed_at >= datetime(today.year, today.month, today.day)
        ).all()
        rev = sum((t.fare or 0) for t in trips)
        return f"Today's revenue: ${rev:,.2f}\nTrips completed: {len(trips)}"

    if cmd.startswith("approve escalation") or re.match(r"^approve\s+\d+$", cmd):
        esc_id = re.search(r"\d+", args or cmd)
        if esc_id:
            return _resolve_escalation(int(esc_id.group()), "approved", db)
        return "Please specify escalation ID. Example: APPROVE 42"

    if cmd.startswith("deny escalation") or re.match(r"^deny\s+\d+$", cmd):
        esc_id = re.search(r"\d+", args or cmd)
        if esc_id:
            return _resolve_escalation(int(esc_id.group()), "denied", db)
        return "Please specify escalation ID. Example: DENY 42"

    if cmd.startswith("suspend driver"):
        driver_name = args.strip() if args else cmd.replace("suspend driver", "").strip()
        return _suspend_driver(driver_name, db)

    if cmd.startswith("activate driver"):
        driver_name = args.strip() if args else cmd.replace("activate driver", "").strip()
        return _activate_driver(driver_name, db)

    if cmd in ("escalations", "pending escalations"):
        pending = db.query(Escalation).filter(Escalation.status == ESC_OPEN).all()
        if not pending:
            return "No pending escalations."
        lines = ["Pending escalations:"]
        for e in pending[:5]:
            lines.append(f"- [{e.id}] {e.reason} ({e.agent})")
        return "\n".join(lines)

    if cmd in ("alerts", "unread alerts"):
        alerts = db.query(Alert).filter_by(is_read=False).order_by(Alert.created_at.desc()).limit(5).all()
        if not alerts:
            return "No unread alerts."
        lines = [f"{len(alerts)} unread alert(s):"]
        for a in alerts:
            lines.append(f"- [{a.severity.upper()}] {a.title}")
        return "\n".join(lines)

    if cmd in ("help", "commands"):
        return (
            "Captain Taxi Commands:\n"
            "- drivers online\n"
            "- revenue today\n"
            "- escalations\n"
            "- alerts\n"
            "- approve [id]\n"
            "- deny [id]\n"
            "- suspend driver [name]\n"
            "- activate driver [name]\n"
            "- Or ask anything naturally!"
        )

    return None


def _resolve_escalation(esc_id: int, decision: str, db: Session) -> str:
    esc = db.query(Escalation).filter_by(id=esc_id).first()
    if not esc:
        return f"Escalation #{esc_id} not found."
    if esc.status != ESC_OPEN:
        return f"Escalation #{esc_id} already resolved."

    esc.status = ESC_RESOLVED
    esc.owner_response = decision
    esc.resolved_at = datetime.utcnow()
    db.commit()

    emoji = "Approved" if decision == "approved" else "Denied"
    return f"{emoji}: Escalation #{esc_id}\n\"{esc.reason}\""


def _suspend_driver(name: str, db: Session) -> str:
    driver = db.query(Driver).filter(Driver.name.ilike(f"%{name}%")).first()
    if not driver:
        return f"Driver '{name}' not found."
    if driver.status == "suspended":
        return f"{driver.name} is already suspended."
    driver.status = "suspended"
    db.commit()
    return f"{driver.name} ({driver.city.title()}) has been suspended."


def _activate_driver(name: str, db: Session) -> str:
    driver = db.query(Driver).filter(Driver.name.ilike(f"%{name}%")).first()
    if not driver:
        return f"Driver '{name}' not found."
    driver.status = "offline"
    db.commit()
    return f"{driver.name} ({driver.city.title()}) has been activated."


async def process_inbound_message(from_number: str, body: str, db: Session) -> str:
    if not is_authorized(from_number):
        return "Sorry, this system is restricted to authorized users only."

    text = body.strip()
    structured_reply = _handle_structured_command(text, "", db)
    if structured_reply is not None:
        return structured_reply

    context = _get_live_context(db)
    return answer_owner_query(text, context)


def register_owner_numbers():
    import os
    for env_key in ("OWNER_WHATSAPP", "AMARA_WHATSAPP"):
        num = os.getenv(env_key, "")
        if num:
            OWNER_NUMBERS.add(num)
            OWNER_NUMBERS.add(num.replace("whatsapp:", ""))
