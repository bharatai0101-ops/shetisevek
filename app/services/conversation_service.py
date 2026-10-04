from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Message
from app.repositories.message_repository import MessageRepository
from app.schemas.message import HistoryMessage


class ConversationService:
    def __init__(self, session: AsyncSession) -> None:
        self.messages = MessageRepository(session)

    async def history(self, inbound: Message) -> list[HistoryMessage]:
        messages = await self.messages.history(inbound)
        return [
            HistoryMessage(role=m.role, message_type=m.message_type, text=m.text_content)
            for m in messages
        ]
