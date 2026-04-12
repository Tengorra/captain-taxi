from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import Integer, String, Numeric, DateTime, Date, Text, Boolean, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from database import Base


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    SENT = "sent"           # QB bill created
    PAID = "paid"
    FAILED = "failed"


class DriverPayment(Base):
    """Weekly payroll record per driver."""
    __tablename__ = "driver_payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    driver_id: Mapped[int] = mapped_column(Integer, __import__("sqlalchemy").ForeignKey("drivers.id"), index=True)

    # Pay period
    week_start: Mapped[date] = mapped_column(Date, index=True)
    week_end: Mapped[date] = mapped_column(Date)

    # Financials
    total_fares: Mapped[Decimal] = mapped_column(Numeric(12, 2))   # sum of trip fares for the week
    total_trips: Mapped[int] = mapped_column(Integer, default=0)
    commission_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4))
    driver_earnings: Mapped[Decimal] = mapped_column(Numeric(12, 2))   # total_fares * commission_rate
    company_cut: Mapped[Decimal] = mapped_column(Numeric(12, 2))        # total_fares * (1 - commission_rate)
    tips: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    net_pay: Mapped[Decimal] = mapped_column(Numeric(12, 2))            # driver_earnings + tips

    status: Mapped[PaymentStatus] = mapped_column(SAEnum(PaymentStatus), default=PaymentStatus.PENDING)

    # QuickBooks contractor payment / bill
    qb_bill_id: Mapped[str | None] = mapped_column(String(100))
    qb_payment_id: Mapped[str | None] = mapped_column(String(100))

    # SMS confirmation
    sms_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sms_message_sid: Mapped[str | None] = mapped_column(String(100))

    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    driver: Mapped["Driver"] = relationship("Driver", back_populates="payments")
