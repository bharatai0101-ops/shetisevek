import logging
from datetime import timedelta
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.constants import DELIVERY_UNCERTAIN, MessageStatus, ProcessingJobStatus
from app.core.exceptions import ExternalError, LostJobClaim
from app.models import ProcessingJob
from app.repositories.job_repository import JobRepository
from app.repositories.message_repository import MessageRepository
from app.repositories.webhook_repository import WebhookRepository
from app.services.message_service import MessageService
from app.utils.datetime import utcnow
from app.utils.retry import backoff_seconds
from app.workers.processor import Processor

logger = logging.getLogger(__name__)


async def record_failure(session: AsyncSession, job_id: UUID, owner: str, exc: Exception) -> None:
    async with session.begin():
        job = await session.get(ProcessingJob, job_id, populate_existing=True)
        if job is None:
            raise LookupError("job_missing")
        if job.locked_by != owner:
            logger.warning("failure_ignored_after_claim_changed", extra={"job_id": job_id})
            return
        reply = await MessageRepository(session).reply(job.message_id)
        # Delivery status can arrive while the sender is still waiting for the HTTP response.
        if reply and reply.whatsapp_message_id:
            job.status = ProcessingJobStatus.COMPLETED
            job.completed_at = utcnow()
            job.last_error = None
        else:
            external = exc if isinstance(exc, ExternalError) else None
            uncertain = (external is not None and external.uncertain) or (
                reply is not None and reply.send_started_at is not None and external is None
            )
            database_retry = isinstance(exc, DBAPIError) and not isinstance(exc, IntegrityError)
            retryable = (
                (external is not None and external.retryable) or database_retry
            ) and not uncertain
            code = external.code if external else "internal_processing_error"
            job.last_error = DELIVERY_UNCERTAIN if uncertain else code
            job.status = (
                ProcessingJobStatus.RETRY
                if retryable and job.attempts < job.max_attempts
                else ProcessingJobStatus.FAILED
            )
            job.available_at = utcnow() + timedelta(seconds=backoff_seconds(job.attempts))
            if reply:
                reply.status = MessageStatus.FAILED
                reply.error_code = job.last_error
                reply.error_message = "Message processing or delivery requires attention"
                if not uncertain:
                    reply.send_started_at = None
                if job.status == ProcessingJobStatus.FAILED:
                    reply.failed_at = utcnow()
        job.locked_at = None
        job.locked_by = None
        logger.warning(
            "retry" if job.status == ProcessingJobStatus.RETRY else "permanent_failure",
            extra={"job_id": job.id, "error_code": job.last_error, "state": job.status.value},
        )


class JobService:
    def __init__(self, engine: AsyncEngine, processor: Processor, worker_id: str) -> None:
        self.engine = engine
        self.processor = processor
        self.worker_id = worker_id

    async def tick(self) -> bool:
        async with self.engine.connect() as connection:
            try:
                async with AsyncSession(bind=connection, expire_on_commit=False) as session:
                    async with session.begin():
                        for event in await WebhookRepository(session).reconcilable():
                            await MessageService(session).apply_status(event)
                    async with session.begin():
                        job = await JobRepository(session).claim(
                            self.worker_id, self.processor.settings.job_stale_seconds
                        )
                    if job is None:
                        return False
                    job_id = job.id
                    logger.info("job_claimed", extra={"job_id": job_id})
                    try:
                        await self.processor.process(session, job)
                    except LostJobClaim:
                        await session.rollback()
                        logger.warning("job_claim_lost", extra={"job_id": job_id})
                    except Exception as exc:
                        await session.rollback()
                        await record_failure(session, job_id, self.worker_id, exc)
                    return True
            finally:
                # Dedicated connection is held across this tick. Always release session locks before
                # returning it to the pool, even if claim commit or failure persistence raised.
                try:
                    if connection.in_transaction():
                        await connection.rollback()
                    await connection.execute(text("SELECT pg_advisory_unlock_all()"))
                    await connection.commit()
                except Exception:
                    logger.error("lock_cleanup_failed", extra={"error_code": "database_connection"})
                    await connection.invalidate()
