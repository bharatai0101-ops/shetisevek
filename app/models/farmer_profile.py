from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.user import User


class FarmerProfile(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "farmer_profiles"
    __table_args__ = (CheckConstraint("farm_size >= 0", name="nonnegative_farm_size"),)

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    preferred_language: Mapped[str | None] = mapped_column(String(64))
    state: Mapped[str | None] = mapped_column(String(128))
    district: Mapped[str | None] = mapped_column(String(128))
    village: Mapped[str | None] = mapped_column(String(128))
    farm_size: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    farm_size_unit: Mapped[str | None] = mapped_column(String(32))
    soil_type: Mapped[str | None] = mapped_column(String(128))
    irrigation_type: Mapped[str | None] = mapped_column(String(128))
    user: Mapped[User] = relationship(back_populates="farmer_profile", lazy="raise")
