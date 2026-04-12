"""
Revenue Reporting Service
==========================
- Daily summary: total trips, total fare, by city — delivered by SMS to owner each night.
- Weekly P&L snapshot — emailed Monday morning.
- Monthly full report — emailed on the 1st.
- Anomaly detection: revenue drop >20% vs previous week → alert owner.
"""
import logging
from datetime import date, timedelta, datetime
from decimal import Decimal

import pandas as pd
from sqlalchemy import func, and_
from sqlalchemy.orm import Session

from config import settings
from models.trip import Trip, TripStatus
from models.expense import Expense
from models.payment import DriverPayment
import services.notifications as notify

logger = logging.getLogger(__name__)


def _trips_query(db: Session, start: date, end: date):
    return (
        db.query(Trip)
        .filter(
            Trip.status == TripStatus.COMPLETED,
            func.date(Trip.completed_at) >= start,
            func.date(Trip.completed_at) <= end,
        )
    )


# ─── Daily Summary ────────────────────────────────────────────────────────────

def daily_revenue_summary(db: Session, ref_date: date | None = None) -> dict:
    """Build daily summary dict. Called each night by scheduler."""
    day = ref_date or date.today() - timedelta(days=1)  # yesterday
    trips = _trips_query(db, day, day).all()

    total_trips = len(trips)
    total_fare = sum(t.fare for t in trips) or Decimal("0.00")
    total_gst = sum(t.gst_amount for t in trips) or Decimal("0.00")
    total_tips = sum(t.tip for t in trips) or Decimal("0.00")

    by_city: dict[str, dict] = {}
    for t in trips:
        city = t.city or "Unknown"
        if city not in by_city:
            by_city[city] = {"trips": 0, "fare": Decimal("0.00")}
        by_city[city]["trips"] += 1
        by_city[city]["fare"] += t.fare

    result = {
        "date": day,
        "total_trips": total_trips,
        "total_fare": total_fare,
        "total_gst": total_gst,
        "total_tips": total_tips,
        "by_city": by_city,
    }

    # SMS owner
    lines = [
        f"Captain Taxi — {day.strftime('%b %d')}",
        f"Trips: {total_trips}",
        f"Revenue: ${total_fare:.2f}",
    ]
    for city, data in by_city.items():
        lines.append(f"  {city}: {data['trips']} trips, ${data['fare']:.2f}")
    try:
        notify.send_sms(settings.owner_phone, "\n".join(lines))
    except Exception as exc:
        logger.error("Daily SMS failed: %s", exc)

    return result


# ─── Weekly P&L ───────────────────────────────────────────────────────────────

def weekly_pnl(db: Session, week_start: date | None = None) -> dict:
    """Calculate P&L for the week. week_start defaults to last Monday."""
    today = date.today()
    mon = week_start or (today - timedelta(days=today.weekday() + 7))
    sun = mon + timedelta(days=6)

    trips = _trips_query(db, mon, sun).all()
    total_revenue = sum(t.fare + t.gst_amount for t in trips) or Decimal("0.00")
    gst_collected = sum(t.gst_amount for t in trips) or Decimal("0.00")
    net_revenue = total_revenue - gst_collected  # revenue before GST

    # Driver pay for the week
    payments = db.query(DriverPayment).filter(DriverPayment.week_start == mon).all()
    total_driver_pay = sum(p.net_pay for p in payments) or Decimal("0.00")

    # Other expenses for the week
    expenses = (
        db.query(Expense)
        .filter(Expense.expense_date >= mon, Expense.expense_date <= sun)
        .all()
    )
    total_expenses = sum(e.amount for e in expenses) or Decimal("0.00")

    gross_profit = net_revenue - total_driver_pay
    net_profit = gross_profit - total_expenses

    result = {
        "week_start": mon,
        "week_end": sun,
        "total_trips": len(trips),
        "gross_revenue": total_revenue,
        "gst_collected": gst_collected,
        "net_revenue": net_revenue,
        "driver_pay": total_driver_pay,
        "other_expenses": total_expenses,
        "gross_profit": gross_profit,
        "net_profit": net_profit,
    }

    # Check for anomaly vs prior week
    prior_mon = mon - timedelta(days=7)
    prior_sun = prior_mon + timedelta(days=6)
    prior_trips = _trips_query(db, prior_mon, prior_sun).all()
    prior_revenue = sum(t.fare for t in prior_trips) or Decimal("0.00")

    if prior_revenue > 0:
        change_pct = float((net_revenue - prior_revenue) / prior_revenue)
        result["revenue_change_pct"] = change_pct
        if change_pct < -settings.revenue_alert_threshold:
            alert = (
                f"ALERT: Captain Taxi revenue dropped {abs(change_pct)*100:.1f}% this week "
                f"(${net_revenue:.0f} vs ${prior_revenue:.0f} last week)."
            )
            logger.warning(alert)
            try:
                notify.send_sms(settings.owner_phone, alert)
                notify.email_owner(subject="Revenue Drop Alert", body=alert)
            except Exception as exc:
                logger.error("Anomaly alert failed: %s", exc)

    # Email weekly P&L to owner
    try:
        _email_weekly_pnl(result)
    except Exception as exc:
        logger.error("Weekly P&L email failed: %s", exc)

    return result


def _email_weekly_pnl(pnl: dict) -> None:
    mon = pnl["week_start"].strftime("%b %d")
    sun = pnl["week_end"].strftime("%b %d")
    change = pnl.get("revenue_change_pct")
    change_str = f"{change*100:+.1f}% vs last week" if change is not None else ""

    body = f"""Captain Taxi — Weekly P&L
Week: {mon} – {sun}
{'=' * 40}
Trips:              {pnl['total_trips']:>10}
Gross Revenue:      ${pnl['gross_revenue']:>9.2f}
GST Collected:      ${pnl['gst_collected']:>9.2f}
Net Revenue:        ${pnl['net_revenue']:>9.2f}  {change_str}
Driver Pay:        -${pnl['driver_pay']:>9.2f}
Other Expenses:    -${pnl['other_expenses']:>9.2f}
{'─' * 40}
Gross Profit:       ${pnl['gross_profit']:>9.2f}
Net Profit:         ${pnl['net_profit']:>9.2f}
"""
    notify.email_owner(subject=f"Captain Taxi — Weekly P&L {mon}–{sun}", body=body)


# ─── Monthly Report ───────────────────────────────────────────────────────────

def monthly_revenue_report(db: Session, month: date | None = None) -> str:
    """Full monthly report emailed to owner on the 1st."""
    import calendar

    ref = month or (date.today().replace(day=1) - timedelta(days=1))
    year, mon = ref.year, ref.month
    first_day = date(year, mon, 1)
    last_day = date(year, mon, calendar.monthrange(year, mon)[1])
    month_label = first_day.strftime("%B %Y")

    trips = _trips_query(db, first_day, last_day).all()
    total_revenue = sum(t.fare + t.gst_amount for t in trips) or Decimal("0.00")
    gst_collected = sum(t.gst_amount for t in trips) or Decimal("0.00")
    net_revenue = total_revenue - gst_collected

    payments = (
        db.query(DriverPayment)
        .filter(DriverPayment.week_start >= first_day, DriverPayment.week_start <= last_day)
        .all()
    )
    total_driver_pay = sum(p.net_pay for p in payments) or Decimal("0.00")

    expenses = (
        db.query(Expense)
        .filter(Expense.expense_date >= first_day, Expense.expense_date <= last_day)
        .all()
    )
    total_expenses = sum(e.amount for e in expenses) or Decimal("0.00")

    # By city
    city_data: dict[str, dict] = {}
    for t in trips:
        city = t.city or "Unknown"
        if city not in city_data:
            city_data[city] = {"trips": 0, "fare": Decimal("0.00")}
        city_data[city]["trips"] += 1
        city_data[city]["fare"] += t.fare

    net_profit = net_revenue - total_driver_pay - total_expenses

    city_lines = "\n".join(
        f"  {city:20s} {d['trips']:>5} trips   ${d['fare']:>10.2f}"
        for city, d in city_data.items()
    )

    report = f"""Captain Taxi — Monthly Report
{month_label}
{'=' * 50}

REVENUE
-------
Trips Completed:    {len(trips):>10}
Gross Revenue:      ${total_revenue:>10.2f}
GST Collected:      ${gst_collected:>10.2f}
Net Revenue:        ${net_revenue:>10.2f}

By City:
{city_lines}

EXPENSES
--------
Driver Pay:         ${total_driver_pay:>10.2f}
Other Expenses:     ${total_expenses:>10.2f}

{'─' * 50}
NET PROFIT:         ${net_profit:>10.2f}

GST Remittance Due: ${gst_collected:>10.2f}
"""

    notify.email_owner(
        subject=f"Captain Taxi — Monthly Report {month_label}",
        body=report,
    )
    logger.info("Monthly report sent for %s", month_label)
    return report
