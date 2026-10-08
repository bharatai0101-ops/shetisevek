from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.utils.datetime import utcnow

if TYPE_CHECKING:
    from app.models.conversation import Conversation
    from app.models.farmer_crop import FarmerCrop
    from app.models.farmer_profile import FarmerProfile


class User(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "users"

    whatsapp_user_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    phone_number: Mapped[str | None] = mapped_column(String(32))
    display_name: Mapped[str | None] = mapped_column(String(256))
    demo_question_count: Mapped[int | None] = mapped_column(BigInteger)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        CheckConstraint("demo_question_count >= 0", name="nonnegative_demo_question_count"),
        Index("ix_users_recent_activity", last_seen_at.desc(), first_seen_at.desc(), "id"),
        Index("ix_users_registration", first_seen_at.desc(), "id"),
    )

    farmer_profile: Mapped[FarmerProfile | None] = relationship(back_populates="user", lazy="raise")
    crops: Mapped[list[FarmerCrop]] = relationship(back_populates="user", lazy="raise")
    conversations: Mapped[list[Conversation]] = relationship(back_populates="user", lazy="raise")
