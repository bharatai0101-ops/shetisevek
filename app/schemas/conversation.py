from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.core.constants import ConversationStatus


class ConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    status: ConversationStatus
