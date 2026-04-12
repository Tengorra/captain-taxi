from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import Integer, String, Numeric, DateTime, Date, Text, Boolean, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column
import enum

from database import Base


class ExpenseCategory(str, enum.Enum):
    FUEL = "fuel"
    MAINTENANCE = "maintenance"
    INSURANCE = "insurance"
    LICENSES = "licenses"
    OFFICE = "office"
    MARKETING = "marketing"
    COMMUNICATIONS = "communications"
    BANK_FEES = "bank_fees"
    PROFESSIONAL = "professional"       # accountant, legal
    OTHER = "other"

    @classmethod
    def qb_account_map(cls) -> dict:
        """Maps category to QuickBooks account name."""
        return {
            cls.FUEL: "Fuel",
            cls.MAINTENANCE: "Vehicle Maintenance & Repairs",
            cls.INSURANCE: "Insurance Expense",
            cls.LICENSES: "Licences & Permits",
            cls.OFFICE: "Office Supplies & Expenses",
            cls.MARKETING: "Advertising & Marketing",
            cls.COMMUNICATIONS: "Telephone & Internet",
            cls.BANK_FEES: "Bank Service Charges",
            cls.PROFESSIONAL: "Professional Fees",
            cls.OTHER: "General & Administrative",
        }


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    gst_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))  # GST paid (input tax credit)

    category: Mapped[ExpenseCategory] = mapped_column(SAEnum(ExpenseCategory), default=ExpenseCategory.OTHER)
    description: Mapped[str | None] = mapped_column(Text)
    vendor: Mapped[str | None] = mapped_column(String(200))
    expense_date: Mapped[date] = mapped_column(Date)

    # Source: receipt image path or email body
    receipt_path: Mapped[str | None] = mapped_column(String(500))
    source: Mapped[str] = mapped_column(String(50), default="manual")  # manual | sms | email

    # AI categorization confidence
    ai_category: Mapped[str | None] = mapped_column(String(100))
    ai_confidence: Mapped[float | None] = mapped_column()
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False)

    # QB
    qb_expense_id: Mapped[str | None] = mapped_column(String(100))
    qb_synced: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    created_by: Mapped[str | None] = mapped_column(String(100))  # owner | amara
