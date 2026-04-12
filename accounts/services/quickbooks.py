"""
QuickBooks Online OAuth2 + API client.

Flow:
  1. GET /accounts/qb/connect  → redirects user to Intuit consent screen
  2. Intuit redirects to /accounts/qb/callback with ?code=...&realmId=...
  3. We exchange code for tokens, store in DB (qb_tokens table)
  4. All subsequent API calls auto-refresh tokens when needed.
"""
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from intuitlib.client import AuthClient
from intuitlib.enums import Scopes
from quickbooks import QuickBooks
from quickbooks.objects.customer import Customer
from quickbooks.objects.vendor import Vendor
from quickbooks.objects.invoice import Invoice as QBInvoice
from quickbooks.objects.detailline import SalesItemLine, SalesItemLineDetail
from quickbooks.objects.item import Item
from quickbooks.objects.bill import Bill
from quickbooks.objects.detailline import AccountBasedExpenseLine, AccountBasedExpenseLineDetail
from quickbooks.objects.bill import AccountBasedExpenseLine as BillLine
from quickbooks.objects.account import Account
from quickbooks.objects.salesreceipt import SalesReceipt
from quickbooks.objects.detailline import SalesItemLine as SalesReceiptLine
from quickbooks.objects.base import Ref
from sqlalchemy.orm import Session

from config import settings
from models.qb_token import QBToken

logger = logging.getLogger(__name__)

GST_RATE = Decimal("0.05")  # 5 % Canadian GST


def _get_auth_client() -> AuthClient:
    return AuthClient(
        client_id=settings.qb_client_id,
        client_secret=settings.qb_client_secret,
        redirect_uri=settings.qb_redirect_uri,
        environment=settings.qb_environment,
    )


def get_authorization_url() -> str:
    """Step 1: URL to send the owner to for QB consent."""
    auth_client = _get_auth_client()
    return auth_client.get_authorization_url(scopes=[Scopes.ACCOUNTING])


def exchange_code_for_tokens(db: Session, code: str, realm_id: str) -> QBToken:
    """Step 2: Exchange authorization code for access + refresh tokens."""
    auth_client = _get_auth_client()
    auth_client.get_bearer_token(code, realm_id=realm_id)

    now = datetime.now(timezone.utc)
    token = db.query(QBToken).filter_by(realm_id=realm_id).first()
    if not token:
        token = QBToken(realm_id=realm_id)
        db.add(token)

    token.access_token = auth_client.access_token
    token.refresh_token = auth_client.refresh_token
    token.access_token_expires_at = now + timedelta(seconds=3600)
    token.refresh_token_expires_at = now + timedelta(days=101)
    db.commit()
    db.refresh(token)
    logger.info("QB tokens stored for realm %s", realm_id)
    return token


def _refresh_if_needed(db: Session, token: QBToken) -> QBToken:
    now = datetime.now(timezone.utc)
    if token.access_token_expires_at.replace(tzinfo=timezone.utc) - now < timedelta(minutes=5):
        auth_client = _get_auth_client()
        auth_client.refresh(token.refresh_token)
        token.access_token = auth_client.access_token
        token.refresh_token = auth_client.refresh_token
        token.access_token_expires_at = now + timedelta(seconds=3600)
        db.commit()
        db.refresh(token)
        logger.info("QB access token refreshed for realm %s", token.realm_id)
    return token


def get_qb_client(db: Session) -> QuickBooks:
    """Return an authenticated QuickBooks client, refreshing tokens if needed."""
    realm_id = settings.qb_realm_id
    token = db.query(QBToken).filter_by(realm_id=realm_id).first()
    if not token:
        raise RuntimeError("QuickBooks not connected. Visit /accounts/qb/connect to authorize.")

    token = _refresh_if_needed(db, token)
    auth_client = _get_auth_client()
    auth_client.access_token = token.access_token
    auth_client.realm_id = realm_id

    return QuickBooks(
        auth_client=auth_client,
        refresh_token=token.refresh_token,
        company_id=realm_id,
    )


# ─── Income: Trip Sales Receipt ───────────────────────────────────────────────

def push_trip_income(
    db: Session,
    *,
    trip_id: int,
    fare: Decimal,
    gst: Decimal,
    tip: Decimal,
    payment_method: str,
    trip_date: datetime,
    driver_name: str,
    city: str,
) -> str:
    """Create a Sales Receipt in QB for a completed trip. Returns QB id."""
    qb = get_qb_client(db)

    receipt = SalesReceipt()
    receipt.TxnDate = trip_date.strftime("%Y-%m-%d")
    receipt.PrivateNote = f"Trip #{trip_id} — {city} — Driver: {driver_name}"

    line = SalesReceiptLine()
    line.Amount = float(fare + gst + tip)
    line.DetailType = "SalesItemLineDetail"
    detail = SalesItemLineDetail()
    detail.UnitPrice = float(fare)
    detail.Qty = 1

    # Item ref: "Taxi Fare" (must exist in QB chart of accounts)
    item_ref = Ref()
    item_ref.name = "Taxi Fare"
    detail.ItemRef = item_ref
    line.SalesItemLineDetail = detail
    receipt.Line = [line]

    receipt.save(qb=qb)
    logger.info("QB sales receipt created: %s for trip %s", receipt.Id, trip_id)
    return receipt.Id


# ─── Expense: Contractor Payment (Driver Pay) ─────────────────────────────────

def push_driver_payment(
    db: Session,
    *,
    driver_qb_vendor_id: str,
    driver_name: str,
    amount: Decimal,
    week_start: str,
    week_end: str,
) -> str:
    """Create a Bill (accounts payable) for a driver's weekly contractor pay. Returns QB bill id."""
    qb = get_qb_client(db)

    bill = Bill()
    bill.VendorRef = Ref()
    bill.VendorRef.value = driver_qb_vendor_id
    bill.TxnDate = week_end
    bill.DueDate = week_end
    bill.PrivateNote = f"Driver pay: {driver_name} | {week_start} – {week_end}"

    line = BillLine()
    line.Amount = float(amount)
    line.DetailType = "AccountBasedExpenseLineDetail"
    detail = AccountBasedExpenseLineDetail()

    acct_ref = Ref()
    acct_ref.name = "Subcontractors"
    detail.AccountRef = acct_ref
    line.AccountBasedExpenseLineDetail = detail
    bill.Line = [line]

    bill.save(qb=qb)
    logger.info("QB bill created: %s for driver %s", bill.Id, driver_name)
    return bill.Id


# ─── Invoice: Corporate Client ────────────────────────────────────────────────

def push_corporate_invoice(
    db: Session,
    *,
    qb_customer_id: str,
    invoice_number: str,
    line_items: list[dict],   # [{"description": ..., "amount": Decimal}]
    gst_amount: Decimal,
    due_date: str,
    period: str,
) -> str:
    """Create an Invoice in QB for a corporate account. Returns QB invoice id."""
    qb = get_qb_client(db)

    inv = QBInvoice()
    inv.DocNumber = invoice_number
    inv.DueDate = due_date
    inv.CustomerRef = Ref()
    inv.CustomerRef.value = qb_customer_id
    inv.PrivateNote = f"Period: {period}"

    lines = []
    for item in line_items:
        line = SalesItemLine()
        line.Amount = float(item["amount"])
        line.DetailType = "SalesItemLineDetail"
        detail = SalesItemLineDetail()
        detail.UnitPrice = float(item["amount"])
        detail.Qty = 1
        item_ref = Ref()
        item_ref.name = "Taxi Fare"
        detail.ItemRef = item_ref
        line.SalesItemLineDetail = detail
        line.Description = item["description"]
        lines.append(line)

    # GST line
    if gst_amount > 0:
        gst_line = SalesItemLine()
        gst_line.Amount = float(gst_amount)
        gst_line.DetailType = "SalesItemLineDetail"
        gst_detail = SalesItemLineDetail()
        gst_detail.UnitPrice = float(gst_amount)
        gst_detail.Qty = 1
        gst_ref = Ref()
        gst_ref.name = "GST Collected"
        gst_detail.ItemRef = gst_ref
        gst_line.SalesItemLineDetail = gst_detail
        gst_line.Description = "GST (5%)"
        lines.append(gst_line)

    inv.Line = lines
    inv.save(qb=qb)
    logger.info("QB invoice created: %s (%s)", inv.Id, invoice_number)
    return inv.Id


# ─── Expense: General Company Expense ────────────────────────────────────────

def push_expense(
    db: Session,
    *,
    amount: Decimal,
    account_name: str,
    description: str,
    expense_date: str,
    vendor_name: str | None = None,
) -> str:
    """Create a Bill for a general company expense. Returns QB bill id."""
    qb = get_qb_client(db)

    bill = Bill()
    bill.TxnDate = expense_date
    bill.PrivateNote = description

    if vendor_name:
        # Try to find vendor by name, create if missing
        vendors = Vendor.filter(Where=f"DisplayName = '{vendor_name}'", qb=qb)
        if vendors:
            bill.VendorRef = Ref()
            bill.VendorRef.value = vendors[0].Id

    line = BillLine()
    line.Amount = float(amount)
    line.DetailType = "AccountBasedExpenseLineDetail"
    detail = AccountBasedExpenseLineDetail()
    acct_ref = Ref()
    acct_ref.name = account_name
    detail.AccountRef = acct_ref
    line.AccountBasedExpenseLineDetail = detail
    line.Description = description
    bill.Line = [line]

    bill.save(qb=qb)
    return bill.Id


# ─── Vendor: Ensure driver exists as QB Vendor ────────────────────────────────

def ensure_driver_vendor(db: Session, *, driver_id: int, full_name: str, email: str | None) -> str:
    """Find or create a QB Vendor for a driver contractor. Returns QB vendor id."""
    qb = get_qb_client(db)

    vendors = Vendor.filter(Where=f"DisplayName = '{full_name}'", qb=qb)
    if vendors:
        return vendors[0].Id

    v = Vendor()
    v.DisplayName = full_name
    if email:
        v.PrimaryEmailAddr = Ref()
        v.PrimaryEmailAddr.Address = email
    v.save(qb=qb)
    logger.info("QB vendor created for driver %s: %s", driver_id, v.Id)
    return v.Id


# ─── Customer: Ensure corporate account exists as QB Customer ─────────────────

def ensure_corporate_customer(db: Session, *, name: str, email: str) -> str:
    """Find or create a QB Customer for a corporate account. Returns QB customer id."""
    qb = get_qb_client(db)

    customers = Customer.filter(Where=f"DisplayName = '{name}'", qb=qb)
    if customers:
        return customers[0].Id

    c = Customer()
    c.DisplayName = name
    c.PrimaryEmailAddr = Ref()
    c.PrimaryEmailAddr.Address = email
    c.save(qb=qb)
    logger.info("QB customer created: %s → %s", name, c.Id)
    return c.Id
