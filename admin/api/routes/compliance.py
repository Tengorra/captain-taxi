from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime, date, timedelta
from ...db.database import get_db
from ...db.models import Driver, Document

router = APIRouter(prefix="/compliance", tags=["compliance"])

DOC_TYPES = ["license", "abstract", "insurance", "taxi_permit", "vehicle_inspection"]


@router.get("/overview")
def get_compliance_overview(db: Session = Depends(get_db)):
    """Traffic light compliance overview for all drivers."""
    drivers = db.query(Driver).filter(Driver.status != "suspended").all()
    today = date.today()
    warning_cutoff = today + timedelta(days=30)
    expiring_cutoff = today + timedelta(days=14)

    result = []
    for driver in drivers:
        raw_docs = db.query(Document).filter(
            Document.entity_id == driver.id,
            Document.entity_type == "driver"
        ).all()
        docs = {d.doc_type: d for d in raw_docs}
        doc_statuses = {}
        overall = "green"

        for doc_type in DOC_TYPES:
            doc = docs.get(doc_type)
            if not doc:
                doc_statuses[doc_type] = "missing"
                overall = "red"
            elif doc.status == "expired" or (doc.expiry_date and doc.expiry_date < today):
                doc_statuses[doc_type] = "expired"
                overall = "red"
            elif doc.expiry_date and doc.expiry_date < expiring_cutoff:
                doc_statuses[doc_type] = "expiring_soon"
                if overall == "green":
                    overall = "amber"
            elif doc.expiry_date and doc.expiry_date < warning_cutoff:
                doc_statuses[doc_type] = "expiring"
                if overall == "green":
                    overall = "amber"
            else:
                doc_statuses[doc_type] = "valid"

        result.append({
            "driver_id": driver.id,
            "driver_name": driver.name,
            "city": driver.city,
            "overall_status": overall,
            "documents": doc_statuses,
        })

    order = {"red": 0, "amber": 1, "green": 2}
    result.sort(key=lambda x: order[x["overall_status"]])
    return result


@router.get("/expiring")
def get_expiring_documents(days: int = 30, db: Session = Depends(get_db)):
    """Get all driver documents expiring within N days."""
    today = date.today()
    cutoff = today + timedelta(days=days)
    docs = (
        db.query(Document)
        .filter(
            Document.entity_type == "driver",
            Document.expiry_date != None,
            Document.expiry_date <= cutoff,
        )
        .order_by(Document.expiry_date)
        .all()
    )
    result = []
    for doc in docs:
        driver = db.query(Driver).filter_by(id=doc.entity_id).first()
        days_until = (doc.expiry_date - today).days if doc.expiry_date else None
        result.append({
            "document_id": doc.id,
            "driver_id": doc.entity_id,
            "driver_name": driver.name if driver else "Unknown",
            "city": driver.city if driver else None,
            "doc_type": doc.doc_type,
            "expiry_date": doc.expiry_date.isoformat() if doc.expiry_date else None,
            "days_until_expiry": days_until,
            "status": "expired" if days_until is not None and days_until < 0 else (
                "critical" if days_until is not None and days_until < 7 else "expiring"
            ),
        })
    return result
