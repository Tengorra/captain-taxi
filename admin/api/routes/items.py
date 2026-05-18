from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel
from typing import Optional
from ...db.database import get_db
from ...db.models import Item

router = APIRouter(prefix="/items", tags=["items"])


class ItemIn(BaseModel):
    code: str
    name: str
    description: Optional[str] = None
    price: float = 0.0
    taxable: bool = True
    active: bool = True


def _row(i: Item) -> dict:
    return {
        "id": i.id, "code": i.code, "name": i.name, "description": i.description,
        "price": i.price, "taxable": i.taxable, "active": i.active,
        "icabbi_ref": i.icabbi_ref,
    }


@router.get("/")
def list_items(active: Optional[bool] = None, db: Session = Depends(get_db)):
    q = db.query(Item)
    if active is not None: q = q.filter(Item.active == active)
    return [_row(i) for i in q.order_by(Item.code.asc()).all()]


@router.post("/")
def create_item(body: ItemIn, db: Session = Depends(get_db)):
    i = Item(**body.model_dump())
    db.add(i)
    try:
        db.commit(); db.refresh(i)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, f"Item code '{body.code}' already exists")
    return _row(i)


@router.patch("/{iid}")
def update_item(iid: int, body: ItemIn, db: Session = Depends(get_db)):
    i = db.get(Item, iid)
    if not i: raise HTTPException(404, "Item not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(i, k, v)
    db.commit(); db.refresh(i)
    return _row(i)


@router.delete("/{iid}")
def delete_item(iid: int, db: Session = Depends(get_db)):
    i = db.get(Item, iid)
    if not i: raise HTTPException(404, "Item not found")
    db.delete(i); db.commit()
    return {"ok": True}
