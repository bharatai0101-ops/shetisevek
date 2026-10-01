from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.core.constants import MessageType
from app.schemas.whatsapp import StatusPayload


@dataclass(frozen=True)
class IncomingMessage:
    event_key: str
    whatsapp_id: str
    sender: str
    display_name: str | None
    kind: MessageType
    text: str | None
    timestamp: datetime
    raw: dict[str, Any]


@dataclass(frozen=True)
class IncomingStatus:
    event_key: str
    payload: StatusPayload


@dataclass(frozen=True)
class ParsedWebhook:
    messages: list[IncomingMessage]
    statuses: list[IncomingStatus]
