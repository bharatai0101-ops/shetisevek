import hashlib
import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import (
    DELIVERY_UNCERTAIN,
    MessageDirection,
    MessageStatus,
    ProcessingJobStatus,
)
from app.integrations.whatsapp.types import ParsedWebhook
from app.models import Message, WebhookEvent
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.job_repository import JobRepository
from app.repositories.message_repository import MessageRepository
from app.repositories.webhook_repository import WebhookRepository
from app.schemas.whatsapp import StatusPayload
from app.services.user_service import UserService
from app.utils.datetime import utcnow

logger = logging.getLogger(__name__)
STATUS_RANK = {MessageStatus.SENT: 1, MessageStatus.DELIVERED: 2, MessageStatus.READ: 3}


class MessageService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.events = WebhookRepository(session)
        self.messages = MessageRepository(session)
        self.jobs = JobRepository(session)

    async def ingest(self, parsed: ParsedWebhook, max_attempts: int) -> None:
        # Caller owns one transaction; sort users to avoid cross-batch lock-order deadlocks.
        for sender in sorted({event.sender for event in parsed.messages}):
            key = int.from_bytes(
                hashlib.sha256(("ingest:" + sender).encode()).digest()[:8], "big", signed=True
            )
            await self.session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})
        for event in sorted(parsed.messages, key=lambda item: item.sender):
            stored = await self.events.add(event.event_key, "message", event.raw, event.whatsapp_id)
            if stored is None:
                logger.info("duplicate_detected")
                continue
            user = await UserService(self.session).identify(event.sender, event.display_name)
            conversation = await ConversationRepository(self.session).active(user.id)
            message = await self.messages.inbound(event, user.id, conversation.id)
            if message is not None:
                job = await self.jobs.create(message, max_attempts)
                logger.info(
                    "message_persisted", extra={"message_id": message.id, "user_id": user.id}
                )
                logger.info("job_created", extra={"job_id": job.id, "message_id": message.id})
            stored.processed = True
            stored.processed_at = utcnow()
        for status in sorted(parsed.statuses, key=lambda item: item.payload.id):
            stored = await self.events.add(
                status.event_key, "status", status.payload.model_dump(), status.payload.id
            )
            if stored is not None:
                await self.apply_status(stored)
            else:
                logger.info("duplicate_detected")

    async def apply_status(self, event: WebhookEvent) -> bool:
        payload = StatusPayload.model_validate(event.payload)
        if payload.status not in ("sent", "delivered", "read", "failed"):
            event.processed = True
            event.processing_error = "unsupported_status"
            event.processed_at = utcnow()
            return False
        correlation: UUID | None = None
        try:
            if payload.biz_opaque_callback_data:
                correlation = UUID(payload.biz_opaque_callback_data)
        except ValueError:
            pass
        match = Message.whatsapp_message_id == payload.id
        if correlation:
            match = or_(match, Message.id == correlation)
        message = (
            await self.session.scalars(
                select(Message)
                .where(match, Message.direction == MessageDirection.OUTBOUND)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).one_or_none()
        if message is None:
            return False  # Retained for reconciliation after outbound ID is committed.
        if message.whatsapp_message_id and message.whatsapp_message_id != payload.id:
            event.processing_error = "provider_id_mismatch"
            event.processed = True
            event.processed_at = utcnow()
            return False
        message.whatsapp_message_id = payload.id
        timestamp = datetime.fromtimestamp(int(payload.timestamp), timezone.utc)
        status = MessageStatus(payload.status.upper())
        timestamp_field = f"{payload.status}_at"
        current = getattr(message, timestamp_field)
        setattr(message, timestamp_field, min(current, timestamp) if current else timestamp)
        if status == MessageStatus.FAILED:
            if message.status not in (MessageStatus.DELIVERED, MessageStatus.READ):
                message.status = status
            if payload.errors:
                code = payload.errors[0].get("code")
                message.error_code = (
                    str(code)[:128] if isinstance(code, (int, str)) else "meta_failed"
                )
            message.error_message = "Meta reported message delivery failure"
        elif STATUS_RANK.get(status, 0) > STATUS_RANK.get(message.status, 0):
            if (
                message.status != MessageStatus.FAILED
                or message.error_code == DELIVERY_UNCERTAIN
                or status
                in (
                    MessageStatus.DELIVERED,
                    MessageStatus.READ,
                )
            ):
                message.status = status
            if message.error_code == DELIVERY_UNCERTAIN:
                message.error_code = None
                message.error_message = None
                message.failed_at = None
        event.processed = True
        event.processed_at = utcnow()
        if message.reply_to_id:
            job = await self.jobs.for_message(message.reply_to_id)
            if job:
                job.status = ProcessingJobStatus.COMPLETED
                job.completed_at = utcnow()
                job.locked_at = None
                job.locked_by = None
                job.last_error = None
        logger.info("status_updated", extra={"event_id": event.id, "message_id": message.id})
        return True

    async def reconcile(self, provider_id: str) -> None:
        for event in await self.events.pending_statuses(provider_id):
            await self.apply_status(event)
