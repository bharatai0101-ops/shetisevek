from datetime import timedelta
from uuid import UUID

from sqlalchemy import Select, and_, exists, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.constants import DELIVERY_UNCERTAIN
from app.core.constants import ProcessingJobStatus as JobStatus
from app.core.exceptions import LostJobClaim
from app.models import Message, ProcessingJob
from app.utils.crypto import advisory_key
from app.utils.datetime import utcnow


class JobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def ensure_claim(self, job_id: UUID, conversation_id: UUID, owner: str | None) -> None:
        locked = await self.session.scalar(
            text("SELECT pg_try_advisory_lock(:key)"), {"key": advisory_key(conversation_id)}
        )
        current_owner = await self.session.scalar(
            select(ProcessingJob.locked_by).where(
                ProcessingJob.id == job_id, ProcessingJob.status == JobStatus.PROCESSING
            )
        )
        if not locked or owner is None or current_owner != owner:
            raise LostJobClaim()

    async def create(self, message: Message, max_attempts: int) -> ProcessingJob:
        job = ProcessingJob(
            message_id=message.id,
            conversation_id=message.conversation_id,
            message_sequence=message.sequence,
            max_attempts=max_attempts,
        )
        self.session.add(job)
        await self.session.flush()
        return job

    @staticmethod
    def claim_statement(stale_seconds: int) -> Select[tuple[ProcessingJob]]:
        earlier = aliased(ProcessingJob)
        blocking = or_(
            earlier.status.in_([JobStatus.PENDING, JobStatus.RETRY, JobStatus.PROCESSING]),
            and_(earlier.status == JobStatus.FAILED, earlier.last_error == DELIVERY_UNCERTAIN),
        )
        return (
            select(ProcessingJob)
            .where(
                or_(
                    and_(
                        ProcessingJob.status.in_([JobStatus.PENDING, JobStatus.RETRY]),
                        ProcessingJob.available_at <= utcnow(),
                    ),
                    and_(
                        ProcessingJob.status == JobStatus.PROCESSING,
                        ProcessingJob.locked_at < utcnow() - timedelta(seconds=stale_seconds),
                    ),
                ),
                ~exists(
                    select(earlier.id).where(
                        earlier.conversation_id == ProcessingJob.conversation_id,
                        earlier.message_sequence < ProcessingJob.message_sequence,
                        blocking,
                    )
                ),
            )
            .order_by(ProcessingJob.available_at, ProcessingJob.message_sequence)
            .with_for_update(skip_locked=True, of=ProcessingJob)
            .limit(20)
        )

    async def claim(self, worker_id: str, stale_seconds: int) -> ProcessingJob | None:
        for job in await self.session.scalars(self.claim_statement(stale_seconds)):
            locked = await self.session.scalar(
                text("SELECT pg_try_advisory_lock(:key)"),
                {"key": advisory_key(job.conversation_id)},
            )
            if not locked:
                continue
            job.status = JobStatus.PROCESSING
            job.locked_by = worker_id
            job.locked_at = utcnow()
            job.attempts += 1
            await self.session.flush()
            return job
        return None

    async def for_message(self, message_id: UUID) -> ProcessingJob | None:
        return (
            await self.session.scalars(
                select(ProcessingJob).where(ProcessingJob.message_id == message_id)
            )
        ).one_or_none()
