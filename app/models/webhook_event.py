from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDMixin
from app.utils.datetime import utcnow


class WebhookEvent(UUIDMixin, Base):
    __tablename__ = "webhook_events"
    __table_args__ = (Index("ix_webhook_status_pending", "provider_message_id", "processed"),)

    event_key: Mapped[str] = mapped_column(String(768), unique=True)
    event_type: Mapped[str] = mapped_column(String(32))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    processed: Mapped[bool] = mapped_column(Boolean, default=False)
    processing_error: Mapped[str | None] = mapped_column(String(128))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provider_message_id: Mapped[str | None] = mapped_column(String(512))
