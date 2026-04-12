from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from ...db.database import get_db
from ...db.models import Escalation
from ...services.twilio_service import send_owner_alert

router = APIRouter(prefix="/escalations", tags=["escalations"])

# Actual DB status values: open / resolved
STATUS_PENDING = "open"
STATUS_RESOLVED = "resolved"


class EscalationCreate(BaseModel):
    title: str
    description: str
    source_agent: str
    callback_url: Optional[str] = None
    metadata: Optional[dict] = {}
    expires_hours: Optional[int] = 4


class EscalationDecision(BaseModel):
    decision: str   # approved | denied
    note: Optional[str] = None


def _esc_dict(e: Escalation) -> dict:
    """Map actual DB schema to the dashboard's expected structure."""
    # Map 'open' → 'pending', 'resolved' → depends on owner_response
    if e.status == STATUS_PENDING:
        dash_status = "pending"
    elif e.owner_response and e.owner_response.startswith("approved"):
        dash_status = "approved"
    elif e.owner_response and e.owner_response.startswith("denied"):
        dash_status = "denied"
    else:
        dash_status = "resolved"

    return {
        "id": e.id,
        "title": e.reason,
        "description": e.details,
        "source_agent": e.agent,
        "status": dash_status,
        "decision": e.owner_response,
        "decision_note": None,
        "created_at": e.created_at.isoformat() if e.created_at else None,
        "resolved_at": e.resolved_at.isoformat() if e.resolved_at else None,
        "expires_at": None,
    }


@router.get("/")
def list_escalations(status: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(Escalation)
    if status == "pending":
        q = q.filter(Escalation.status == STATUS_PENDING)
    elif status and status != "pending":
        q = q.filter(Escalation.status == STATUS_RESOLVED)
    escalations = q.order_by(Escalation.created_at.desc()).limit(50).all()
    return [_esc_dict(e) for e in escalations]


@router.post("/")
def create_escalation(body: EscalationCreate, db: Session = Depends(get_db)):
    """Called by other agents to escalate a decision."""
    esc = Escalation(
        agent=body.source_agent,
        reason=body.title,
        details=body.description,
        priority="high",
        status=STATUS_PENDING,
    )
    db.add(esc)
    db.commit()
    db.refresh(esc)

    try:
        from ...agents.admin_agent import format_escalation_for_owner
        msg = format_escalation_for_owner({
            "id": esc.id,
            "title": body.title,
            "description": body.description,
            "source_agent": body.source_agent,
            "metadata": body.metadata,
        })
        send_owner_alert(msg)
    except Exception as e:
        print(f"[Escalation] WhatsApp send error: {e}")

    return {"id": esc.id, "status": "pending", "message": "Escalation created"}


@router.get("/{esc_id}")
def get_escalation(esc_id: int, db: Session = Depends(get_db)):
    esc = db.query(Escalation).filter_by(id=esc_id).first()
    if not esc:
        raise HTTPException(404, "Escalation not found")
    return _esc_dict(esc)


@router.post("/{esc_id}/decide")
def decide_escalation(esc_id: int, body: EscalationDecision, db: Session = Depends(get_db)):
    """Dashboard approve/deny handler."""
    esc = db.query(Escalation).filter_by(id=esc_id).first()
    if not esc:
        raise HTTPException(404, "Escalation not found")
    if esc.status != STATUS_PENDING:
        raise HTTPException(400, "Escalation already resolved")
    if body.decision not in ("approved", "denied"):
        raise HTTPException(400, "Decision must be 'approved' or 'denied'")

    response = body.decision
    if body.note:
        response = f"{body.decision}: {body.note}"

    esc.status = STATUS_RESOLVED
    esc.owner_response = response
    esc.resolved_at = datetime.utcnow()
    db.commit()

    return {"ok": True, "decision": body.decision}


@router.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request, db: Session = Depends(get_db)):
    """Twilio webhook for inbound WhatsApp messages."""
    form = await request.form()
    from_number = form.get("From", "")
    body_text = form.get("Body", "").strip()

    from ...agents.whatsapp_handler import process_inbound_message
    reply = await process_inbound_message(from_number, body_text, db)

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Message>{reply}</Message>
</Response>"""
    from fastapi.responses import Response
    return Response(content=twiml, media_type="application/xml")
