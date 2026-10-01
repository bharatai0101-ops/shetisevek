from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.constants import ProcessingJobStatus
from app.db.base import Base, TimestampMixin, UUIDMixin
from app.utils.datetime import utcnow


class ProcessingJob(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "processing_jobs"
    __table_args__ = (
        Index("ix_jobs_poll", "status", "available_at"),
        Index("ix_jobs_conversation_order", "conversation_id", "message_sequence"),
        CheckConstraint("attempts >= 0 AND max_attempts > 0", name="valid_attempts"),
    )

    message_id: Mapped[UUID] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), unique=True
    )
    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE")
    )
    message_sequence: Mapped[int] = mapped_column(BigInteger)
    job_type: Mapped[str] = mapped_column(String(32), default="GENERATE_AND_SEND")
    status: Mapped[ProcessingJobStatus] = mapped_column(
        Enum(ProcessingJobStatus, name="processing_job_status"), default=ProcessingJobStatus.PENDING
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    locked_by: Mapped[str | None] = mapped_column(String(128))
    last_error: Mapped[str | None] = mapped_column(String(128))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
