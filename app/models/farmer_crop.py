from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import FarmerCropStatus
from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.user import User


class FarmerCrop(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "farmer_crops"
    __table_args__ = (CheckConstraint("area >= 0", name="nonnegative_area"),)

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    crop_name: Mapped[str] = mapped_column(String(128))
    variety: Mapped[str | None] = mapped_column(String(128))
    season: Mapped[str | None] = mapped_column(String(64))
    sowing_date: Mapped[date | None] = mapped_column(Date)
    area: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    area_unit: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[FarmerCropStatus] = mapped_column(
        Enum(FarmerCropStatus, name="farmer_crop_status"), default=FarmerCropStatus.ACTIVE
    )
    source_message_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL", use_alter=True), unique=True
    )
    user: Mapped[User] = relationship(back_populates="crops", lazy="raise")
