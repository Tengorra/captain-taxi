from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel
from typing import Optional, List, Any
from ...db.database import get_db
from ...db.models import CustomFieldDef, CustomFieldValue

router = APIRouter(prefix="/custom-fields", tags=["custom-fields"])


class FieldDefIn(BaseModel):
    entity_type: str
    key: str
    label: str
    data_type: Optional[str] = "string"
    options: Optional[List[Any]] = None
    required: Optional[bool] = False


class FieldValueIn(BaseModel):
    field_id: int
    entity_id: str
    value: Optional[str] = None


def _def_row(d: CustomFieldDef) -> dict:
    return {
        "id": d.id, "entity_type": d.entity_type, "key": d.key, "label": d.label,
        "data_type": d.data_type, "options": d.options or [], "required": d.required,
        "icabbi_ref": d.icabbi_ref,
    }


# ─── definitions ────────────────────────────────────────────────────────────

@router.get("/defs")
def list_defs(entity_type: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(CustomFieldDef)
    if entity_type: q = q.filter(CustomFieldDef.entity_type == entity_type)
    return [_def_row(d) for d in q.order_by(CustomFieldDef.id.asc()).all()]


@router.post("/defs")
def create_def(body: FieldDefIn, db: Session = Depends(get_db)):
    d = CustomFieldDef(**body.model_dump())
    db.add(d)
    try:
        db.commit(); db.refresh(d)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, f"Field '{body.entity_type}.{body.key}' already exists")
    return _def_row(d)


@router.delete("/defs/{did}")
def delete_def(did: int, db: Session = Depends(get_db)):
    d = db.get(CustomFieldDef, did)
    if not d: raise HTTPException(404, "Field definition not found")
    db.query(CustomFieldValue).filter(CustomFieldValue.field_id == did).delete()
    db.delete(d); db.commit()
    return {"ok": True}


# ─── values ─────────────────────────────────────────────────────────────────

@router.get("/values")
def list_values(entity_id: str, db: Session = Depends(get_db)):
    rows = db.query(CustomFieldValue).filter(CustomFieldValue.entity_id == entity_id).all()
    return [{"id": r.id, "field_id": r.field_id, "entity_id": r.entity_id, "value": r.value}
            for r in rows]


@router.put("/values")
def upsert_value(body: FieldValueIn, db: Session = Depends(get_db)):
    existing = db.query(CustomFieldValue).filter_by(
        field_id=body.field_id, entity_id=body.entity_id
    ).first()
    if existing:
        existing.value = body.value
    else:
        existing = CustomFieldValue(**body.model_dump())
        db.add(existing)
    db.commit(); db.refresh(existing)
    return {"id": existing.id, "field_id": existing.field_id,
            "entity_id": existing.entity_id, "value": existing.value}
