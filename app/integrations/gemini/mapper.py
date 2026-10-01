from google.genai import types

from app.core.constants import MessageRole, MessageType
from app.schemas.message import HistoryMessage


def map_history(history: list[HistoryMessage], char_limit: int) -> list[types.Content]:
    reversed_contents: list[types.Content] = []
    remaining = char_limit
    for message in reversed(history):
        if message.role == MessageRole.SYSTEM or remaining <= 0:
            continue
        text = message.text or ""
        if message.message_type not in (
            MessageType.TEXT,
            MessageType.BUTTON,
            MessageType.INTERACTIVE,
        ):
            kind = message.message_type.value.lower()
            text = f"[Received {kind} metadata; media unavailable.] {text}"
        text = text[:remaining]
        remaining -= len(text)
        if text:
            reversed_contents.append(
                types.Content(
                    role="model" if message.role == MessageRole.ASSISTANT else "user",
                    parts=[types.Part(text=text)],
                )
            )
    contents = list(reversed(reversed_contents))
    while contents and contents[0].role == "model":
        contents.pop(0)
    return contents
