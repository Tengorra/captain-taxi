"""
Expense Tracking Service
=========================
- Owner / Amara can SMS or email a receipt → agent reads it,
  uses Claude to categorize it, and enters it in QuickBooks.
- Monthly expense report delivered to owner by email.
"""
import base64
import logging
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import anthropic
from sqlalchemy.orm import Session

from config import settings
from models.expense import Expense, ExpenseCategory
import services.quickbooks as qb_service
import services.notifications as notify

logger = logging.getLogger(__name__)
_claude = anthropic.Anthropic(api_key=settings.anthropic_api_key)


# ─── AI Categorization ────────────────────────────────────────────────────────

_CATEGORY_PROMPT = """
You are an accountant for Captain Taxi, a taxi company in Saskatoon and Regina, Saskatchewan, Canada.

Given the following receipt text or description, extract and return JSON with these fields:
- amount: float (CAD, excluding GST if GST is listed separately)
- gst_amount: float (CAD GST paid, 0 if not visible)
- vendor: string (merchant name)
- expense_date: string (YYYY-MM-DD, use today if not found)
- category: one of [fuel, maintenance, insurance, licenses, office, marketing, communications, bank_fees, professional, other]
- description: string (brief description of what was purchased)
- confidence: float 0-1 (how confident you are in the categorization)

Receipt text:
{text}

Today's date: {today}

Return ONLY valid JSON, no explanation.
"""


def categorize_receipt_text(text: str) -> dict:
    """Ask Claude to extract expense details from receipt text."""
    today = date.today().isoformat()
    msg = _claude.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=400,
        messages=[{"role": "user", "content": _CATEGORY_PROMPT.format(text=text, today=today)}],
    )
    import json
    raw = msg.content[0].text.strip()
    return json.loads(raw)


def categorize_receipt_image(image_path: str) -> dict:
    """Ask Claude vision to extract expense details from a receipt image."""
    import json
    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")

    suffix = Path(image_path).suffix.lower()
    media_type_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".pdf": "application/pdf"}
    media_type = media_type_map.get(suffix, "image/jpeg")

    today = date.today().isoformat()
    msg = _claude.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=400,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_data}},
                {"type": "text", "text": _CATEGORY_PROMPT.format(text="[see image above]", today=today)},
            ],
        }],
    )
    raw = msg.content[0].text.strip()
    return json.loads(raw)


# ─── Expense Entry ────────────────────────────────────────────────────────────

def record_expense(
    db: Session,
    *,
    text: str | None = None,
    image_path: str | None = None,
    source: str = "manual",
    created_by: str = "owner",
) -> Expense:
    """
    Main entry point: given receipt text or image, categorize and save.
    Pushes to QuickBooks automatically.
    """
    if image_path:
        data = categorize_receipt_image(image_path)
    elif text:
        data = categorize_receipt_text(text)
    else:
        raise ValueError("Provide either text or image_path")

    # Map AI category string to enum
    try:
        category = ExpenseCategory(data.get("category", "other"))
    except ValueError:
        category = ExpenseCategory.OTHER

    expense_date_str = data.get("expense_date") or date.today().isoformat()
    try:
        expense_date = date.fromisoformat(expense_date_str)
    except ValueError:
        expense_date = date.today()

    expense = Expense(
        amount=Decimal(str(data.get("amount", 0))),
        gst_amount=Decimal(str(data.get("gst_amount", 0))),
        category=category,
        description=data.get("description"),
        vendor=data.get("vendor"),
        expense_date=expense_date,
        receipt_path=image_path,
        source=source,
        ai_category=data.get("category"),
        ai_confidence=data.get("confidence"),
        created_by=created_by,
    )
    db.add(expense)
    db.flush()

    # Push to QuickBooks
    account_map = ExpenseCategory.qb_account_map()
    account_name = account_map.get(category, "General & Administrative")
    try:
        qb_id = qb_service.push_expense(
            db,
            amount=expense.amount,
            account_name=account_name,
            description=expense.description or f"{category.value} expense",
            expense_date=expense_date.isoformat(),
            vendor_name=expense.vendor,
        )
        expense.qb_expense_id = qb_id
        expense.qb_synced = True
    except Exception as exc:
        logger.error("QB expense push failed: %s", exc)

    db.commit()
    logger.info(
        "Expense recorded: $%s %s from %s (QB: %s)",
        expense.amount, category.value, expense.vendor, expense.qb_expense_id
    )
    return expense


# ─── Monthly Expense Report ───────────────────────────────────────────────────

def generate_monthly_expense_report(db: Session, month: date | None = None) -> str:
    """
    Aggregate expenses for the given month (default: last month).
    Returns a formatted text summary and emails it to the owner.
    """
    import calendar
    import pandas as pd

    ref = month or date.today().replace(day=1) - __import__("datetime").timedelta(days=1)
    year, mon = ref.year, ref.month
    first_day = date(year, mon, 1)
    last_day = date(year, mon, calendar.monthrange(year, mon)[1])

    expenses = (
        db.query(Expense)
        .filter(Expense.expense_date >= first_day, Expense.expense_date <= last_day)
        .all()
    )

    if not expenses:
        return f"No expenses recorded for {first_day.strftime('%B %Y')}."

    rows = [
        {"category": e.category.value, "amount": float(e.amount), "gst": float(e.gst_amount), "vendor": e.vendor}
        for e in expenses
    ]
    df = pd.DataFrame(rows)
    by_category = df.groupby("category")["amount"].sum().sort_values(ascending=False)

    total = df["amount"].sum()
    total_gst = df["gst"].sum()

    lines = [f"Expense Report — {first_day.strftime('%B %Y')}", "=" * 40]
    for cat, amt in by_category.items():
        lines.append(f"  {cat.title():25s} ${amt:>10.2f}")
    lines += [
        "-" * 40,
        f"  {'TOTAL':25s} ${total:>10.2f}",
        f"  {'GST (input credits)':25s} ${total_gst:>10.2f}",
        f"  {'Net (excl. GST)':25s} ${total - total_gst:>10.2f}",
    ]
    report = "\n".join(lines)

    notify.email_owner(
        subject=f"Captain Taxi — Expense Report {first_day.strftime('%B %Y')}",
        body=report,
    )
    return report
