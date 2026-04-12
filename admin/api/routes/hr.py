from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from ...db.database import get_db
from ...db.models import Driver
from ...agents.admin_agent import draft_hr_document

router = APIRouter(prefix="/hr", tags=["hr"])


class HRDocumentRequest(BaseModel):
    doc_type: str  # offer_letter | warning_letter | policy_update | termination
    driver_id: Optional[str] = None
    context: dict = {}


@router.post("/draft")
def draft_document(body: HRDocumentRequest, db: Session = Depends(get_db)):
    """Draft an HR document using Claude. Owner reviews before sending."""
    ctx = dict(body.context)
    if body.driver_id:
        driver = db.query(Driver).filter_by(id=body.driver_id).first()
        if driver:
            ctx["driver_name"] = driver.name
            ctx["driver_city"] = driver.city.title() if driver.city else ""
            ctx["driver_phone"] = driver.phone

    content = draft_hr_document(body.doc_type, ctx)
    return {
        "doc_type": body.doc_type,
        "content": content,
        "driver_id": body.driver_id,
        "note": "Review this draft before sending. Edit as needed."
    }
