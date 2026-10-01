from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError

from app.core.constants import MessageType
from app.core.exceptions import ValidationFailure
from app.integrations.whatsapp.types import IncomingMessage, IncomingStatus, ParsedWebhook
from app.schemas.whatsapp import WebhookEnvelope
from app.utils.crypto import event_digest


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def extract_text(raw: dict[str, Any]) -> str | None:
    kind = raw.get("type")
    text: Any = None
    if kind == "text":
        text = as_dict(raw.get("text")).get("body")
    elif kind == "button":
        text = as_dict(raw.get("button")).get("text")
    elif kind == "interactive":
        data = as_dict(raw.get("interactive"))
        text = as_dict(data.get(str(data.get("type")))).get("title")
    elif kind in ("image", "video", "document"):
        text = as_dict(raw.get(kind)).get("caption")
    return text if isinstance(text, str) else None


def parse_webhook(raw_body: bytes, phone_id: str, business_id: str) -> ParsedWebhook:
    try:
        envelope = WebhookEnvelope.model_validate_json(raw_body)
    except ValidationError:
        raise ValidationFailure() from None
    messages: list[IncomingMessage] = []
    statuses: list[IncomingStatus] = []
    for entry in envelope.entry:
        if entry.id != business_id:
            continue
        for change in entry.changes:
            value = change.value
            if change.field != "messages" or value.metadata.get("phone_number_id") != phone_id:
                continue
            names = {c.get("wa_id"): as_dict(c.get("profile")).get("name") for c in value.contacts}
            for message in value.messages:
                raw = message.model_dump(by_alias=True)
                name = names.get(message.sender)
                kind = message.type.upper()
                if kind == "CONTACTS":
                    kind = "CONTACT"
                try:
                    message_type = MessageType(kind)
                except ValueError:
                    message_type = MessageType.UNKNOWN
                messages.append(
                    IncomingMessage(
                        event_key=f"message:{phone_id}:{message.id}",
                        whatsapp_id=message.id,
                        sender=message.sender,
                        display_name=name[:256] if isinstance(name, str) else None,
                        kind=message_type,
                        text=extract_text(raw),
                        raw=raw,
                        timestamp=datetime.fromtimestamp(int(message.timestamp), timezone.utc),
                    )
                )
            for status in value.statuses:
                statuses.append(
                    IncomingStatus(
                        event_key=f"status:{phone_id}:" + event_digest(status.model_dump()),
                        payload=status,
                    )
                )
    return ParsedWebhook(messages, statuses)
