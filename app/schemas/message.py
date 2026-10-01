from pydantic import BaseModel

from app.core.constants import MessageRole, MessageType


class HistoryMessage(BaseModel):
    role: MessageRole
    message_type: MessageType
    text: str | None
