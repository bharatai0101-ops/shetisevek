import logging
from datetime import timedelta
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.constants import MessageStatus, ProcessingJobStatus
from app.core.exceptions import ExternalError, PermanentExternalError
from app.integrations.whatsapp.client import WhatsAppClient
from app.models import ProcessingJob
from app.repositories.job_repository import JobRepository
from app.repositories.message_repository import MessageRepository
from app.repositories.user_repository import UserRepository
from app.schemas.farmer import CropCreate, FarmerProfileUpdate
from app.services.chatbot_service import ChatbotService
from app.services.conversation_service import ConversationService
from app.services.crop_service import CropService
from app.services.farmer_service import FarmerService
from app.services.message_service import MessageService
from app.utils.datetime import utcnow

logger = logging.getLogger(__name__)


class Processor:
    def __init__(
        self, settings: Settings, chatbot: ChatbotService, whatsapp: WhatsAppClient
    ) -> None:
        self.settings = settings
        self.chatbot = chatbot
        self.whatsapp = whatsapp

    async def explicit_update(
        self, session: AsyncSession, user_id: UUID, message_id: UUID, text: str
    ) -> str | None:
        try:
            if text.startswith("/profile "):
                data = FarmerProfileUpdate.model_validate_json(text[len("/profile ") :])
                await FarmerService(session).update_explicit(user_id, data)
                return "Farmer explicitly supplied profile fields; they were saved successfully."
            if text.startswith("/crop "):
                crop = CropCreate.model_validate_json(text[len("/crop ") :])
                await CropService(session).add_explicit(user_id, crop, message_id)
                return "Farmer explicitly supplied a crop record; it was saved successfully."
        except ValidationError:
            return "Invalid profile/crop command; nothing changed. Explain JSON fields briefly."
        return None

    async def process(self, session: AsyncSession, job: ProcessingJob) -> None:
        messages = MessageRepository(session)
        jobs = JobRepository(session)
        job_id, conversation_id, owner = job.id, job.conversation_id, job.locked_by
        async with session.begin():
            await jobs.ensure_claim(job_id, conversation_id, owner)
            inbound = await messages.get(job.message_id)
            outbound = await messages.reply(inbound.id)
            if outbound and outbound.whatsapp_message_id:
                job.status = ProcessingJobStatus.COMPLETED
                job.completed_at = utcnow()
                job.locked_at = None
                job.locked_by = None
                return
            if outbound and outbound.send_started_at:
                raise ExternalError("delivery_uncertain", uncertain=True)
            if job.attempts > job.max_attempts:
                raise PermanentExternalError("attempts_exhausted")
            if inbound.provider_timestamp and inbound.provider_timestamp < utcnow() - timedelta(
                hours=23
            ):
                raise PermanentExternalError("customer_service_window_expired")
            if inbound.user_id is None:
                raise PermanentExternalError("inbound_user_missing")
            user = await UserRepository(session).get(inbound.user_id)
            if outbound is None:
                command_result = await self.explicit_update(
                    session, user.id, inbound.id, inbound.text_content or ""
                )
                farmer = await FarmerService(session).context(user.id)
                history = await ConversationService(session).history(
                    inbound, self.settings.conversation_history_limit
                )
        if outbound is None:
            # No database transaction is held across generation; conversation advisory lock remains.
            text = await self.chatbot.reply(history, farmer, len(history) == 1, command_result)
            async with session.begin():
                await jobs.ensure_claim(job_id, conversation_id, owner)
                outbound = await messages.assistant(inbound, text)
            logger.info(
                "assistant_message_persisted", extra={"message_id": outbound.id, "job_id": job.id}
            )
        async with session.begin():
            await jobs.ensure_claim(job_id, conversation_id, owner)
            outbound = await messages.get(outbound.id, lock=True)
            if outbound.whatsapp_message_id:
                return
            if outbound.send_started_at:
                raise ExternalError("delivery_uncertain", uncertain=True)
            outbound.status = MessageStatus.PENDING_SEND
            outbound.send_started_at = utcnow()
            outbound.error_code = None
            outbound.error_message = None
        # Committed send intent: a crash/timeout requires reconciliation before retry.
        provider_id, payload = await self.whatsapp.send_text(
            user.whatsapp_user_id, outbound.text_content or "", outbound.id
        )
        async with session.begin():
            outbound = await messages.get(outbound.id, lock=True)
            if outbound.whatsapp_message_id and outbound.whatsapp_message_id != provider_id:
                raise ExternalError("provider_id_mismatch", uncertain=True)
            outbound.whatsapp_message_id = provider_id
            outbound.raw_payload = payload
            outbound.sent_at = outbound.sent_at or utcnow()
            if outbound.status in (MessageStatus.GENERATED, MessageStatus.PENDING_SEND):
                outbound.status = MessageStatus.SENT
            await MessageService(session).reconcile(provider_id)
            job.status = ProcessingJobStatus.COMPLETED
            job.completed_at = utcnow()
            job.locked_at = None
            job.locked_by = None
            job.last_error = None
        logger.info("job_completed", extra={"job_id": job.id, "message_id": outbound.id})
