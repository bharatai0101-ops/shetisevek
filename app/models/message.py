from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Identity, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.constants import MessageDirection, MessageRole, MessageStatus, MessageType
from app.db.base import Base, TimestampMixin, UUIDMixin


class Message(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_messages_conversation_sequence", "conversation_id", "sequence"),
        Index(
            "ix_messages_direction_created_at", "direction", "created_at", postgresql_include=["id"]
        ),
    )

    sequence: Mapped[int] = mapped_column(BigInteger, Identity(), unique=True)
    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    whatsapp_message_id: Mapped[str | None] = mapped_column(String(512), unique=True)
    direction: Mapped[MessageDirection] = mapped_column(
        Enum(MessageDirection, name="message_direction")
    )
    role: Mapped[MessageRole] = mapped_column(Enum(MessageRole, name="message_role"))
    message_type: Mapped[MessageType] = mapped_column(Enum(MessageType, name="message_type"))
    text_content: Mapped[str | None] = mapped_column(Text)
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    status: Mapped[MessageStatus] = mapped_column(Enum(MessageStatus, name="message_status"))
    error_code: Mapped[str | None] = mapped_column(String(128))
    error_message: Mapped[str | None] = mapped_column(String(256))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provider_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reply_to_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), unique=True
    )
    send_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
