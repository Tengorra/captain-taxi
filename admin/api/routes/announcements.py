from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from ...db.database import get_db
from ...db.models import Driver, Announcement
from ...services.twilio_service import broadcast_sms

router = APIRouter(prefix="/announcements", tags=["announcements"])


class AnnouncementCreate(BaseModel):
    message: str
    target_city: Optional[str] = None  # None = all cities


@router.post("/send")
def send_announcement(body: AnnouncementCreate, db: Session = Depends(get_db)):
    """Blast a message to all active drivers via SMS."""
    q = db.query(Driver).filter(Driver.status != "suspended")
    if body.target_city:
        q = q.filter(Driver.city == body.target_city)
    drivers = q.all()

    phones = [d.phone for d in drivers if d.phone]
    if not phones:
        raise HTTPException(400, "No drivers to message")

    results = broadcast_sms(phones, body.message)
    sent = sum(1 for r in results.values() if r["status"] == "sent")
    failed = len(phones) - sent

    announcement = Announcement(
        message=body.message,
        target_city=body.target_city,
        delivery_count=sent,
    )
    db.add(announcement)
    db.commit()

    return {
        "ok": True,
        "sent": sent,
        "failed": failed,
        "total_drivers": len(phones),
        "details": results,
    }


@router.get("/history")
def get_announcement_history(limit: int = 20, db: Session = Depends(get_db)):
    announcements = db.query(Announcement).order_by(Announcement.sent_at.desc()).limit(limit).all()
    return [
        {
            "id": a.id,
            "message": a.message,
            "target_city": a.target_city,
            "delivery_count": a.delivery_count,
            "sent_at": a.sent_at.isoformat() if a.sent_at else None,
        }
        for a in announcements
    ]
