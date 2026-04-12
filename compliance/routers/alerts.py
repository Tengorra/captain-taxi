from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from compliance.database import get_db
from compliance.services.alerts import send_owner_alert

router = APIRouter(prefix="/compliance/alerts", tags=["alerts"])


class ManualAlertRequest(BaseModel):
    subject: str
    body: str


@router.post("/owner")
async def send_manual_alert(
    data: ManualAlertRequest, db: AsyncSession = Depends(get_db)
):
    await send_owner_alert(db, subject=data.subject, body=data.body)
    return {"message": "Alert sent to owner"}
