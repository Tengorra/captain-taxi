from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime, date, timedelta
from ...db.database import get_db, redis_client
from ...db.models import Trip, Driver, Alert, Escalation

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

TRIP_COMPLETED = "completed"
TRIP_IN_PROGRESS = "in_progress"


@router.get("/overview")
def get_overview(db: Session = Depends(get_db)):
    """Live overview stats for the dashboard home page."""
    today = date.today()
    today_start = datetime(today.year, today.month, today.day)

    # Today's trips and revenue
    today_trips = db.query(Trip).filter(
        Trip.status == TRIP_COMPLETED,
        Trip.completed_at >= today_start
    ).all()
    today_revenue = sum((t.fare or 0) for t in today_trips)

    # Live driver counts from Redis (fallback to DB)
    try:
        sk_online = int(redis_client.get("drivers:online:saskatoon") or 0)
        reg_online = int(redis_client.get("drivers:online:regina") or 0)
        sk_active_trips = int(redis_client.get("trips:active:saskatoon") or 0)
        reg_active_trips = int(redis_client.get("trips:active:regina") or 0)
    except Exception:
        sk_online = db.query(Driver).filter(
            Driver.city == "saskatoon", Driver.status == "active"
        ).count()
        reg_online = db.query(Driver).filter(
            Driver.city == "regina", Driver.status == "active"
        ).count()
        sk_active_trips = db.query(Trip).filter(
            Trip.city == "saskatoon", Trip.status == TRIP_IN_PROGRESS
        ).count()
        reg_active_trips = db.query(Trip).filter(
            Trip.city == "regina", Trip.status == TRIP_IN_PROGRESS
        ).count()

    # Alerts
    unread_alerts = db.query(Alert).filter_by(is_read=False, is_resolved=False).count()
    critical_alerts = db.query(Alert).filter(
        Alert.is_read == False,
        Alert.is_resolved == False,
        Alert.severity.in_(["high", "critical"])
    ).count()

    # Pending escalations
    pending_escalations = db.query(Escalation).filter(
        Escalation.status == "open"
    ).count()

    # Yesterday comparison
    yesterday = today - timedelta(days=1)
    yesterday_start = datetime(yesterday.year, yesterday.month, yesterday.day)
    yesterday_trips = db.query(Trip).filter(
        Trip.status == TRIP_COMPLETED,
        Trip.completed_at >= yesterday_start,
        Trip.completed_at < today_start
    ).all()
    yesterday_revenue = sum((t.fare or 0) for t in yesterday_trips)

    revenue_change = 0.0
    if yesterday_revenue > 0:
        revenue_change = round(((today_revenue - yesterday_revenue) / yesterday_revenue) * 100, 1)

    return {
        "drivers_online": {
            "saskatoon": sk_online,
            "regina": reg_online,
            "total": sk_online + reg_online,
        },
        "active_trips": {
            "saskatoon": sk_active_trips,
            "regina": reg_active_trips,
            "total": sk_active_trips + reg_active_trips,
        },
        "today": {
            "trips": len(today_trips),
            "revenue": round(today_revenue, 2),
            "revenue_change_pct": revenue_change,
        },
        "alerts": {
            "unread": unread_alerts,
            "critical": critical_alerts,
        },
        "pending_escalations": pending_escalations,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/alerts")
def get_alerts(limit: int = 20, db: Session = Depends(get_db)):
    alerts = (
        db.query(Alert)
        .filter_by(is_resolved=False)
        .order_by(Alert.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": a.id,
            "title": a.title,
            "message": a.message,
            "severity": a.severity,
            "source_agent": a.source_agent,
            "is_read": a.is_read,
            "driver_id": a.driver_id,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in alerts
    ]


@router.post("/alerts/{alert_id}/read")
def mark_alert_read(alert_id: int, db: Session = Depends(get_db)):
    alert = db.query(Alert).filter_by(id=alert_id).first()
    if alert:
        alert.is_read = True
        db.commit()
    return {"ok": True}


@router.post("/alerts/{alert_id}/resolve")
def resolve_alert(alert_id: int, db: Session = Depends(get_db)):
    alert = db.query(Alert).filter_by(id=alert_id).first()
    if alert:
        alert.is_resolved = True
        alert.is_read = True
        db.commit()
    return {"ok": True}


@router.get("/revenue/chart")
def get_revenue_chart(days: int = 7, db: Session = Depends(get_db)):
    result = []
    for i in range(days - 1, -1, -1):
        day = date.today() - timedelta(days=i)
        start = datetime(day.year, day.month, day.day)
        end = start + timedelta(days=1)
        trips = db.query(Trip).filter(
            Trip.status == TRIP_COMPLETED,
            Trip.completed_at >= start,
            Trip.completed_at < end
        ).all()
        result.append({
            "date": day.isoformat(),
            "label": day.strftime("%a"),
            "revenue": round(sum((t.fare or 0) for t in trips), 2),
            "trips": len(trips),
        })
    return result
