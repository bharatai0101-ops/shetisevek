from datetime import date

from sqlalchemy import BigInteger, Date, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DashboardDailyCount(Base):
    __tablename__ = "dashboard_daily_counts"

    kind: Mapped[str] = mapped_column(Text, primary_key=True)
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    count: Mapped[int] = mapped_column(BigInteger)
