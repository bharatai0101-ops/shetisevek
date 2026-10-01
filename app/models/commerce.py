from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class Deal(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "deals"
    __table_args__ = (CheckConstraint('"end" >= start', name="valid_deal_dates"),)

    title: Mapped[str] = mapped_column(String(200))
    partner: Mapped[str] = mapped_column(String(200))
    company_name: Mapped[str] = mapped_column(String(200))
    contact_person: Mapped[str] = mapped_column(String(128), default="")
    phone: Mapped[str] = mapped_column(String(32), default="")
    email: Mapped[str] = mapped_column(String(200), default="")
    gst_number: Mapped[str] = mapped_column(String(32), default="")
    address: Mapped[str] = mapped_column(Text, default="")
    region: Mapped[str] = mapped_column(String(128), index=True)
    start: Mapped[date] = mapped_column(Date)
    end: Mapped[date] = mapped_column(Date)
    terms: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="Active")


class DealRedemption(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "deal_redemptions"
    __table_args__ = (CheckConstraint("quantity > 0", name="positive_quantity"),)

    deal_id: Mapped[UUID] = mapped_column(ForeignKey("deals.id", ondelete="CASCADE"), index=True)
    occurred_on: Mapped[date] = mapped_column(Date, index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1)


class FinanceEntry(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "finance_entries"
    __table_args__ = (
        CheckConstraint("amount >= 0 AND tax >= 0", name="nonnegative_money"),
        CheckConstraint("kind IN ('revenue', 'expense', 'payout')", name="valid_finance_kind"),
    )

    occurred_on: Mapped[date] = mapped_column(Date, index=True)
    kind: Mapped[str] = mapped_column(String(32))
    category: Mapped[str] = mapped_column(String(128))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    tax: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    paid: Mapped[bool] = mapped_column(default=False)
