from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import ConversationStatus
from app.models import Conversation
from app.utils.datetime import utcnow


class ConversationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def active(self, user_id: UUID) -> Conversation:
        await self.session.execute(
            insert(Conversation)
            .values(
                user_id=user_id,
                status=ConversationStatus.ACTIVE,
                started_at=utcnow(),
                last_message_at=utcnow(),
            )
            .on_conflict_do_nothing(
                index_elements=[Conversation.user_id], index_where=text("status = 'ACTIVE'")
            )
        )
        conversation = (
            await self.session.scalars(
                select(Conversation).where(
                    Conversation.user_id == user_id,
                    Conversation.status == ConversationStatus.ACTIVE,
                )
            )
        ).one()
        conversation.last_message_at = utcnow()
        return conversation
