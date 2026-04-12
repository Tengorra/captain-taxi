"""
Tax Compliance Service (Canadian)
===================================
- GST: 5% collected on fares. Quarterly remittance summary.
- T4A: Annual contractor payment summary for each driver (reminder in February).
- Both delivered to owner via email.

GST periods (calendar year):
  Q1 Jan 1 – Mar 31  → due Apr 30
  Q2 Apr 1 – Jun 30  → due Jul 31
  Q3 Jul 1 – Sep 30  → due Oct 31
  Q4 Oct 1 – Dec 31  → due Jan 31 next year
"""
import logging
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session
from sqlalchemy import func

from config import settings
from models.trip import Trip, TripStatus
from models.payment import DriverPayment
from models.expense import Expense
import services.notifications as notify

logger = logging.getLogger(__name__)

GST_RATE = Decimal("0.05")

_GST_QUARTERS = [
    (1, 1, 3, 31),   # Q1: Jan 1 – Mar 31
    (4, 1, 6, 30),   # Q2: Apr 1 – Jun 30
    (7, 1, 9, 30),   # Q3: Jul 1 – Sep 30
    (10, 1, 12, 31), # Q4: Oct 1 – Dec 31
]


def _quarter_for_date(d: date) -> tuple[date, date, date]:
    """Returns (period_start, period_end, due_date) for the quarter containing d."""
    for q_start_m, q_start_d, q_end_m, q_end_d in _GST_QUARTERS:
        start = date(d.year, q_start_m, q_start_d)
        end = date(d.year, q_end_m, q_end_d)
        if start <= d <= end:
            # Due date is last day of the month following the quarter
            next_m = q_end_m + 1 if q_end_m < 12 else 1
            next_y = d.year if q_end_m < 12 else d.year + 1
            due = date(next_y, next_m, 30)  # approximate; could use calendar.monthrange
            return start, end, due
    raise ValueError(f"No quarter found for date {d}")


def quarterly_gst_summary(db: Session, ref_date: date | None = None) -> dict:
    """
    Generate GST remittance summary for the most recently completed quarter.
    Called by scheduler on the 1st of the month after each quarter ends.
    Returns summary dict and emails it to owner.
    """
    # Default: use the last completed quarter
    today = ref_date or date.today()
    # Step back one day to get the last completed quarter
    end_of_last_quarter = today - timedelta(days=1)
    period_start, period_end, due_date = _quarter_for_date(end_of_last_quarter)

    trips = (
        db.query(Trip)
        .filter(
            Trip.status == TripStatus.COMPLETED,
            func.date(Trip.completed_at) >= period_start,
            func.date(Trip.completed_at) <= period_end,
        )
        .all()
    )

    total_fares = sum(t.fare for t in trips) or Decimal("0.00")
    gst_collected = sum(t.gst_amount for t in trips) or Decimal("0.00")

    # GST paid on expenses (Input Tax Credits — ITCs)
    expenses = (
        db.query(Expense)
        .filter(Expense.expense_date >= period_start, Expense.expense_date <= period_end)
        .all()
    )
    itc = sum(e.gst_amount for e in expenses) or Decimal("0.00")

    net_gst_owing = gst_collected - itc

    summary = {
        "period": f"{period_start} – {period_end}",
        "period_start": period_start,
        "period_end": period_end,
        "due_date": due_date,
        "total_fares": total_fares,
        "gst_collected": gst_collected,
        "itc": itc,
        "net_gst_owing": net_gst_owing,
        "gst_number": settings.company_gst_number,
    }

    body = f"""Captain Taxi — GST Remittance Summary
GST Number: {settings.company_gst_number}
Period: {period_start.strftime('%b %d, %Y')} – {period_end.strftime('%b %d, %Y')}
Due Date: {due_date.strftime('%B %d, %Y')}
{'=' * 50}

Total Fares:             ${total_fares:>10.2f}
GST Collected (Line 105): ${gst_collected:>10.2f}

Input Tax Credits (ITCs): ${itc:>10.2f}
  (GST paid on business expenses)

{'─' * 50}
NET GST OWING (Line 109): ${net_gst_owing:>10.2f}

ACTION: Log into CRA My Business Account and remit ${net_gst_owing:.2f} by {due_date.strftime('%B %d, %Y')}.
Payment options: My Business Account, online banking (CRA as payee).
"""

    notify.email_owner(
        subject=f"GST Remittance Due by {due_date.strftime('%b %d, %Y')} — ${net_gst_owing:.2f}",
        body=body,
    )
    if settings.amara_email:
        notify.send_email(
            to_email=settings.amara_email,
            to_name="Amara",
            subject=f"GST Remittance Due by {due_date.strftime('%b %d, %Y')} — ${net_gst_owing:.2f}",
            body=body,
        )

    logger.info("GST summary emailed: owing $%s due %s", net_gst_owing, due_date)
    return summary


def t4a_reminder(db: Session) -> None:
    """
    Called each February 1st.
    Generates a T4A summary for each active driver for the prior calendar year.
    T4A must be filed by the last day of February.
    """
    today = date.today()
    prior_year = today.year - 1
    year_start = date(prior_year, 1, 1)
    year_end = date(prior_year, 12, 31)

    payments = (
        db.query(DriverPayment)
        .filter(
            DriverPayment.week_start >= year_start,
            DriverPayment.week_start <= year_end,
        )
        .all()
    )

    # Group by driver
    driver_totals: dict[int, Decimal] = {}
    driver_names: dict[int, str] = {}
    driver_info: dict[int, object] = {}
    for p in payments:
        driver_totals[p.driver_id] = driver_totals.get(p.driver_id, Decimal("0.00")) + p.net_pay
        driver_names[p.driver_id] = p.driver.full_name
        driver_info[p.driver_id] = p.driver

    t4a_threshold = Decimal("500.00")  # CRA requires T4A for contractor payments ≥ $500

    lines = [f"T4A Summary — Tax Year {prior_year}", "=" * 50]
    eligible = {did: amt for did, amt in driver_totals.items() if amt >= t4a_threshold}

    for driver_id, total in sorted(eligible.items(), key=lambda x: driver_names[x[0]]):
        driver = driver_info[driver_id]
        lines.append(
            f"  {driver_names[driver_id]:30s} ${total:>10.2f}  "
            f"SIN: {getattr(driver, 'sin', 'NOT ON FILE') or 'NOT ON FILE'}"
        )

    lines += [
        "",
        f"Total eligible drivers: {len(eligible)}",
        f"T4A filing deadline: February 28, {today.year}",
        "",
        "ACTION ITEMS:",
        "1. Log into CRA My Business Account → Payroll → T4A slips",
        "2. Enter each contractor above and their box 48 (Fees for services) amount",
        "3. Submit by February 28",
        "4. Provide copy to each driver by February 28",
    ]

    body = "\n".join(lines)
    notify.email_owner(
        subject=f"ACTION REQUIRED: T4A Filing Due Feb 28, {today.year}",
        body=body,
    )
    logger.info("T4A reminder sent: %d eligible drivers for %d", len(eligible), prior_year)
