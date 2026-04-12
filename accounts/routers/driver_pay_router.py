"""Driver pay endpoints."""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from models.driver import Driver, DriverStatus
from models.payment import DriverPayment
import services.driver_pay as pay_service

router = APIRouter(prefix="/driver-pay", tags=["Driver Pay"])


@router.post("/run-payroll")
def run_payroll(week_start: Optional[date] = Query(None), db: Session = Depends(get_db)):
    """Manually trigger payroll for a specific week (or last full week if not specified)."""
    payments = pay_service.run_weekly_payroll(db, week_start=week_start)
    return {
        "processed": len(payments),
        "payments": [
            {
                "driver_id": p.driver_id,
                "driver": p.driver.full_name,
                "week": f"{p.week_start} – {p.week_end}",
                "trips": p.total_trips,
                "net_pay": float(p.net_pay),
                "status": p.status,
                "qb_bill_id": p.qb_bill_id,
            }
            for p in payments
        ],
    }


@router.get("/preview")
def preview_payroll(week_start: Optional[date] = Query(None), db: Session = Depends(get_db)):
    """Preview payroll figures without writing anything."""
    mon, sun = pay_service._get_week_range(week_start)
    drivers = db.query(Driver).filter_by(status=DriverStatus.ACTIVE).all()
    previews = []
    for driver in drivers:
        p = pay_service.calculate_driver_pay(db, driver, mon, sun)
        if p["total_trips"] > 0:
            previews.append({
                "driver_id": driver.id,
                "driver": driver.full_name,
                "trips": p["total_trips"],
                "total_fares": float(p["total_fares"]),
                "commission_rate": float(p["commission_rate"]),
                "driver_earnings": float(p["driver_earnings"]),
                "tips": float(p["tips"]),
                "net_pay": float(p["net_pay"]),
                "company_cut": float(p["company_cut"]),
            })
    return {"week": f"{mon} – {sun}", "drivers": previews}


@router.get("/history")
def payment_history(
    driver_id: Optional[int] = Query(None),
    limit: int = Query(20, le=100),
    db: Session = Depends(get_db),
):
    q = db.query(DriverPayment)
    if driver_id:
        q = q.filter_by(driver_id=driver_id)
    payments = q.order_by(DriverPayment.week_start.desc()).limit(limit).all()
    return [
        {
            "id": p.id,
            "driver": p.driver.full_name,
            "week": f"{p.week_start} – {p.week_end}",
            "trips": p.total_trips,
            "net_pay": float(p.net_pay),
            "status": p.status,
            "sms_sent": p.sms_sent_at is not None,
        }
        for p in payments
    ]
