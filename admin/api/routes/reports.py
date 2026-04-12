from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from datetime import datetime, date, timedelta
import io
from ...db.database import get_db
from ...db.models import Trip, Driver
from ...services.pdf_service import generate_weekly_report

router = APIRouter(prefix="/reports", tags=["reports"])

TRIP_COMPLETED = "completed"


@router.get("/revenue")
def get_revenue_report(
    start_date: str = Query(..., description="YYYY-MM-DD"),
    end_date: str = Query(..., description="YYYY-MM-DD"),
    city: str = Query(None),
    db: Session = Depends(get_db)
):
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)

    q = db.query(Trip).filter(
        Trip.status == TRIP_COMPLETED,
        Trip.completed_at >= start,
        Trip.completed_at < end
    )
    if city:
        q = q.filter(Trip.city == city)

    trips = q.all()
    total_revenue = sum((t.fare or 0) for t in trips)
    company_revenue = total_revenue * 0.30
    driver_pay = total_revenue * 0.70

    by_city: dict = {}
    for t in trips:
        c = t.city or "unknown"
        if c not in by_city:
            by_city[c] = {"trips": 0, "revenue": 0.0}
        by_city[c]["trips"] += 1
        by_city[c]["revenue"] += t.fare or 0

    daily: dict = {}
    for t in trips:
        if t.completed_at:
            day = t.completed_at.date().isoformat()
            if day not in daily:
                daily[day] = {"trips": 0, "revenue": 0.0}
            daily[day]["trips"] += 1
            daily[day]["revenue"] += t.fare or 0

    return {
        "start_date": start_date,
        "end_date": end_date,
        "total_trips": len(trips),
        "total_revenue": round(total_revenue, 2),
        "company_revenue": round(company_revenue, 2),
        "driver_pay": round(driver_pay, 2),
        "by_city": {k: {"trips": v["trips"], "revenue": round(v["revenue"], 2)}
                    for k, v in by_city.items()},
        "daily": {k: {"trips": v["trips"], "revenue": round(v["revenue"], 2)}
                  for k, v in sorted(daily.items())},
    }


@router.get("/weekly/download")
def download_weekly_report(
    week_offset: int = Query(0),
    db: Session = Depends(get_db)
):
    today = date.today()
    week_start = today - timedelta(days=today.weekday() + 7 + (week_offset * 7))
    week_end = week_start + timedelta(days=6)
    start_dt = datetime(week_start.year, week_start.month, week_start.day)
    end_dt = datetime(week_end.year, week_end.month, week_end.day, 23, 59, 59)

    trips = db.query(Trip).filter(
        Trip.status == TRIP_COMPLETED,
        Trip.completed_at >= start_dt,
        Trip.completed_at <= end_dt
    ).all()

    sk_trips = [t for t in trips if t.city == "saskatoon"]
    reg_trips = [t for t in trips if t.city == "regina"]
    sk_gross = sum((t.fare or 0) for t in sk_trips)
    reg_gross = sum((t.fare or 0) for t in reg_trips)

    drivers = db.query(Driver).all()
    driver_stats = []
    for d in drivers:
        drv_trips = [t for t in trips if t.driver_id == d.id]
        if drv_trips:
            driver_stats.append({
                "name": d.name,
                "city": d.city,
                "trips": len(drv_trips),
                "earnings": round(sum((t.fare or 0) for t in drv_trips) * 0.70, 2),
                "score": d.performance_score if d.performance_score is not None else 100.0,
                "status": d.status,
            })
    driver_stats.sort(key=lambda x: x["trips"], reverse=True)

    week_label = f"{week_start.strftime('%b %d')} – {week_end.strftime('%b %d, %Y')}"
    data = {
        "week_label": week_label,
        "saskatoon": {"trips": len(sk_trips), "gross": round(sk_gross, 2),
                      "driver_pay": round(sk_gross * 0.70, 2), "company": round(sk_gross * 0.30, 2)},
        "regina": {"trips": len(reg_trips), "gross": round(reg_gross, 2),
                   "driver_pay": round(reg_gross * 0.70, 2), "company": round(reg_gross * 0.30, 2)},
        "total_trips": len(trips),
        "total_gross": round(sk_gross + reg_gross, 2),
        "total_driver_pay": round((sk_gross + reg_gross) * 0.70, 2),
        "total_company": round((sk_gross + reg_gross) * 0.30, 2),
        "drivers": driver_stats,
        "compliance_issues": [],
    }

    pdf_bytes = generate_weekly_report(data)
    filename = f"captain-taxi-{week_label.replace(' ', '-').replace('–', 'to')}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
