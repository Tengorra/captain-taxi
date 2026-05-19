from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from ...db.database import get_db
from ...db.models import Settings

router = APIRouter(prefix="/settings", tags=["settings"])


class SettingUpdate(BaseModel):
    value: str


@router.get("/")
def get_all_settings(db: Session = Depends(get_db)):
    settings = db.query(Settings).all()
    return {s.key: {"value": s.value, "description": s.description} for s in settings}


@router.get("/{key}")
def get_setting(key: str, db: Session = Depends(get_db)):
    s = db.query(Settings).filter_by(key=key).first()
    if not s:
        raise HTTPException(404, f"Setting '{key}' not found")
    return {"key": s.key, "value": s.value, "description": s.description}


@router.put("/{key}")
def update_setting(key: str, body: SettingUpdate, db: Session = Depends(get_db)):
    s = db.query(Settings).filter_by(key=key).first()
    if not s:
        s = Settings(key=key, value=body.value)
        db.add(s)
    else:
        s.value = body.value
    db.commit()
    return {"ok": True, "key": key, "value": body.value}


@router.get("/commission/rates")
def get_commission_rates(db: Session = Depends(get_db)):
    sk = db.query(Settings).filter_by(key="commission_rate_saskatoon").first()
    reg = db.query(Settings).filter_by(key="commission_rate_regina").first()
    return {
        "saskatoon": float(sk.value) if sk else 0.30,
        "regina": float(reg.value) if reg else 0.30,
    }
