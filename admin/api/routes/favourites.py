from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from ...db.database import get_db
from ...db.models import Favourite

router = APIRouter(prefix="/favourites", tags=["favourites"])


class FavouriteIn(BaseModel):
    customer_id: str
    label: str
    address_text: str
    lat: Optional[float] = None
    lng: Optional[float] = None
    address_id: Optional[int] = None


def _row(f: Favourite) -> dict:
    return {
        "id": f.id, "customer_id": f.customer_id, "label": f.label,
        "address_text": f.address_text, "lat": f.lat, "lng": f.lng,
        "address_id": f.address_id, "times_used": f.times_used,
        "icabbi_ref": f.icabbi_ref,
        "created_at": f.created_at.isoformat() if f.created_at else None,
    }


@router.get("/")
def list_favourites(customer_id: Optional[str] = None, limit: int = 200,
                    db: Session = Depends(get_db)):
    q = db.query(Favourite)
    if customer_id: q = q.filter(Favourite.customer_id == customer_id)
    return [_row(f) for f in q.order_by(Favourite.times_used.desc()).limit(limit).all()]


@router.post("/")
def create_favourite(body: FavouriteIn, db: Session = Depends(get_db)):
    f = Favourite(**body.model_dump())
    db.add(f); db.commit(); db.refresh(f)
    return _row(f)


@router.post("/{fid}/touch")
def increment_use(fid: int, db: Session = Depends(get_db)):
    f = db.get(Favourite, fid)
    if not f: raise HTTPException(404, "Favourite not found")
    f.times_used = (f.times_used or 0) + 1
    db.commit()
    return {"ok": True, "times_used": f.times_used}


@router.delete("/{fid}")
def delete_favourite(fid: int, db: Session = Depends(get_db)):
    f = db.get(Favourite, fid)
    if not f: raise HTTPException(404, "Favourite not found")
    db.delete(f); db.commit()
    return {"ok": True}
