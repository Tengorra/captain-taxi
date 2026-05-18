from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List, Any
from ...db.database import get_db
from ...db.models import Area

router = APIRouter(prefix="/areas", tags=["areas"])


class AreaIn(BaseModel):
    name: str
    area_type: Optional[str] = "circle"   # circle / polygon
    city: Optional[str] = None
    center_lat: Optional[float] = None
    center_lng: Optional[float] = None
    radius_m: Optional[int] = None
    polygon_geojson: Optional[Any] = None
    tags: Optional[List[str]] = None
    active: Optional[bool] = True


def _row(a: Area) -> dict:
    return {
        "id": a.id, "name": a.name, "area_type": a.area_type, "city": a.city,
        "center_lat": a.center_lat, "center_lng": a.center_lng, "radius_m": a.radius_m,
        "polygon_geojson": a.polygon_geojson, "tags": a.tags or [], "active": a.active,
        "icabbi_ref": a.icabbi_ref,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


@router.get("/")
def list_areas(city: Optional[str] = None, active: Optional[bool] = None,
               db: Session = Depends(get_db)):
    q = db.query(Area)
    if city: q = q.filter(Area.city == city)
    if active is not None: q = q.filter(Area.active == active)
    return [_row(a) for a in q.order_by(Area.id.desc()).all()]


@router.post("/")
def create_area(body: AreaIn, db: Session = Depends(get_db)):
    a = Area(**body.model_dump())
    db.add(a); db.commit(); db.refresh(a)
    return _row(a)


@router.get("/{aid}")
def get_area(aid: int, db: Session = Depends(get_db)):
    a = db.get(Area, aid)
    if not a: raise HTTPException(404, "Area not found")
    return _row(a)


@router.patch("/{aid}")
def update_area(aid: int, body: AreaIn, db: Session = Depends(get_db)):
    a = db.get(Area, aid)
    if not a: raise HTTPException(404, "Area not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(a, k, v)
    db.commit(); db.refresh(a)
    return _row(a)


@router.delete("/{aid}")
def delete_area(aid: int, db: Session = Depends(get_db)):
    a = db.get(Area, aid)
    if not a: raise HTTPException(404, "Area not found")
    db.delete(a); db.commit()
    return {"ok": True}
