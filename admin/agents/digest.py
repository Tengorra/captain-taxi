"""
Digest Agent — Daily 7am WhatsApp digest and Monday weekly email report.
"""
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from ..db.database import SessionLocal, redis_client
from ..db.models import Trip, Driver, Document, Escalation, Alert
from ..services.twilio_service import send_owner_alert
from ..services.sendgrid_service import send_weekly_report
from ..services.pdf_service import generate_weekly_report
from .admin_agent import generate_daily_digest

TRIP_COMPLETED = "completed"
ESC_OPEN = "open"


def _get_yesterday_stats(db: Session) -> dict:
    yesterday = date.today() - timedelta(days=1)
    start = datetime(yesterday.year, yesterday.month, yesterday.day)
    end = datetime(yesterday.year, yesterday.month, yesterday.day, 23, 59, 59)

    trips = db.query(Trip).filter(
        Trip.status == TRIP_COMPLETED,
        Trip.completed_at >= start,
        Trip.completed_at <= end
    ).all()

    sk_trips = [t for t in trips if t.city == "saskatoon"]
    reg_trips = [t for t in trips if t.city == "regina"]
    sk_rev = sum((t.fare or 0) for t in sk_trips)
    reg_rev = sum((t.fare or 0) for t in reg_trips)

    suspended = db.query(Driver).filter(Driver.status == "suspended").count()

    expiry_cutoff = date.today() + timedelta(days=14)
    expiring = db.query(Document).filter(
        Document.entity_type == "driver",
        Document.expiry_date != None,
        Document.expiry_date <= expiry_cutoff,
        Document.status.in_(["expiring", "expired"])
    ).count()

    pending_escalations = db.query(Escalation).filter(Escalation.status == ESC_OPEN).count()
    unread_alerts = db.query(Alert).filter_by(is_read=False, is_resolved=False).count()

    return {
        "date": yesterday.strftime("%B %d, %Y"),
        "saskatoon": {"trips": len(sk_trips), "revenue": round(sk_rev, 2)},
        "regina": {"trips": len(reg_trips), "revenue": round(reg_rev, 2)},
        "total_trips": len(trips),
        "total_revenue": round(sk_rev + reg_rev, 2),
        "suspended_drivers": suspended,
        "expiring_documents": expiring,
        "pending_escalations": pending_escalations,
        "unread_alerts": unread_alerts,
    }


def send_daily_digest():
    db = SessionLocal()
    try:
        stats = _get_yesterday_stats(db)
        message = generate_daily_digest(stats)
        send_owner_alert(message)
        print(f"[Digest] Daily digest sent at {datetime.now().isoformat()}")
    except Exception as e:
        print(f"[Digest] Error sending daily digest: {e}")
        send_owner_alert(f"Captain Taxi: Error generating daily digest.\n{str(e)[:100]}")
    finally:
        db.close()


def _get_weekly_stats(db: Session) -> dict:
    today = date.today()
    week_start = today - timedelta(days=today.weekday() + 7)
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
    total_gross = sk_gross + reg_gross
    commission_rate = 0.30

    drivers = db.query(Driver).all()
    driver_stats = []
    for driver in drivers:
        drv_trips = [t for t in trips if t.driver_id == driver.id]
        earnings = sum((t.fare or 0) for t in drv_trips) * (1 - commission_rate)
        driver_stats.append({
            "name": driver.name,
            "city": driver.city,
            "trips": len(drv_trips),
            "earnings": round(earnings, 2),
            "score": driver.performance_score if driver.performance_score is not None else 100.0,
            "status": driver.status,
        })
    driver_stats.sort(key=lambda x: x["trips"], reverse=True)

    expiry_cutoff = date.today() + timedelta(days=30)
    compliance_docs = db.query(Document).filter(
        Document.entity_type == "driver",
        Document.expiry_date != None,
        Document.expiry_date <= expiry_cutoff
    ).all()
    compliance_issues = []
    for doc in compliance_docs:
        driver = db.query(Driver).filter_by(id=doc.entity_id).first()
        compliance_issues.append({
            "driver_name": driver.name if driver else "Unknown",
            "doc_type": doc.doc_type,
            "status": doc.status,
            "expiry": doc.expiry_date.strftime("%Y-%m-%d") if doc.expiry_date else "N/A",
        })

    week_label = f"{week_start.strftime('%b %d')} – {week_end.strftime('%b %d, %Y')}"
    return {
        "week_label": week_label,
        "saskatoon": {"trips": len(sk_trips), "gross": round(sk_gross, 2),
                      "driver_pay": round(sk_gross * (1 - commission_rate), 2),
                      "company": round(sk_gross * commission_rate, 2)},
        "regina": {"trips": len(reg_trips), "gross": round(reg_gross, 2),
                   "driver_pay": round(reg_gross * (1 - commission_rate), 2),
                   "company": round(reg_gross * commission_rate, 2)},
        "total_trips": len(trips),
        "total_gross": round(total_gross, 2),
        "total_driver_pay": round(total_gross * (1 - commission_rate), 2),
        "total_company": round(total_gross * commission_rate, 2),
        "drivers": driver_stats,
        "compliance_issues": compliance_issues,
    }


def send_weekly_email_report():
    db = SessionLocal()
    try:
        stats = _get_weekly_stats(db)
        pdf_bytes = generate_weekly_report(stats)
        success = send_weekly_report(pdf_bytes, stats["week_label"])
        if success:
            send_owner_alert(
                f"Weekly report for {stats['week_label']} has been emailed.\n"
                f"Total revenue: ${stats['total_gross']:,.2f} | Trips: {stats['total_trips']}"
            )
        print(f"[Digest] Weekly report sent: {success}")
    except Exception as e:
        print(f"[Digest] Error sending weekly report: {e}")
    finally:
        db.close()
