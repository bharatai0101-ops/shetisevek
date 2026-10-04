from datetime import timedelta
from uuid import UUID

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.constants import MessageDirection, MessageRole, MessageStatus, MessageType
from app.integrations.whatsapp.types import IncomingMessage
from app.models import Message


class MessageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def inbound(
        self, event: IncomingMessage, user_id: UUID, conversation_id: UUID
    ) -> Message | None:
        statement = (
            insert(Message)
            .values(
                user_id=user_id,
                conversation_id=conversation_id,
                whatsapp_message_id=event.whatsapp_id,
                direction=MessageDirection.INBOUND,
                role=MessageRole.USER,
                message_type=event.kind,
                text_content=event.text,
                raw_payload=event.raw,
                status=MessageStatus.RECEIVED,
                provider_timestamp=event.timestamp,
            )
            .on_conflict_do_nothing(index_elements=[Message.whatsapp_message_id])
            .returning(Message)
        )
        return (await self.session.scalars(statement)).one_or_none()

    async def get(self, message_id: UUID, lock: bool = False) -> Message:
        statement = select(Message).where(Message.id == message_id)
        if lock:
            statement = statement.with_for_update()
        return (
            await self.session.scalars(statement.execution_options(populate_existing=True))
        ).one()

    async def reply(self, message_id: UUID) -> Message | None:
        return (
            await self.session.scalars(select(Message).where(Message.reply_to_id == message_id))
        ).one_or_none()

    async def assistant(self, inbound: Message, text: str) -> Message:
        statement = (
            insert(Message)
            .values(
                user_id=inbound.user_id,
                conversation_id=inbound.conversation_id,
                direction=MessageDirection.OUTBOUND,
                role=MessageRole.ASSISTANT,
                message_type=MessageType.TEXT,
                text_content=text,
                status=MessageStatus.GENERATED,
                reply_to_id=inbound.id,
            )
            .on_conflict_do_nothing(index_elements=[Message.reply_to_id])
        )
        await self.session.execute(statement)
        reply = await self.reply(inbound.id)
        assert reply is not None
        return reply

    async def history(self, inbound: Message) -> list[Message]:
        parent = aliased(Message)
        logical_order = func.coalesce(parent.sequence, Message.sequence)
        statement = (
            select(Message)
            .outerjoin(parent, Message.reply_to_id == parent.id)
            .where(
                Message.user_id == inbound.user_id,
                func.coalesce(parent.created_at, Message.created_at)
                >= inbound.created_at - timedelta(hours=24),
                or_(
                    and_(
                        Message.direction == MessageDirection.INBOUND,
                        Message.sequence <= inbound.sequence,
                    ),
                    and_(
                        Message.direction == MessageDirection.OUTBOUND,
                        parent.sequence < inbound.sequence,
                        Message.whatsapp_message_id.is_not(None),
                        Message.status != MessageStatus.FAILED,
                    ),
                ),
            )
            .order_by(
                logical_order.desc(),
                case((Message.direction == MessageDirection.OUTBOUND, 1), else_=0).desc(),
            )
        )
        return list(reversed(list(await self.session.scalars(statement))))
