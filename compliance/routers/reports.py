from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from compliance.database import get_db
from compliance.services.report import get_compliance_summary, generate_weekly_report
from compliance.services.sweep import run_daily_sweep

router = APIRouter(prefix="/compliance/reports", tags=["reports"])


@router.get("/summary")
async def compliance_summary(db: AsyncSession = Depends(get_db)):
    return await get_compliance_summary(db)


@router.post("/sweep")
async def trigger_sweep():
    """Manually trigger the compliance sweep (owner use only)."""
    stats = await run_daily_sweep()
    return {"message": "Sweep complete", "stats": stats}


@router.post("/weekly")
async def trigger_weekly_report():
    """Manually trigger the weekly compliance report."""
    report = await generate_weekly_report()
    return {"message": "Report sent", "report": report}
