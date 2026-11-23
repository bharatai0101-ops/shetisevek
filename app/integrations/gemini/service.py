import asyncio
import logging
from datetime import timedelta, timezone

import httpx
from google import genai
from google.genai import errors, types

from app.core.config import Settings
from app.integrations.gemini.exceptions import GeminiError
from app.integrations.gemini.mapper import map_history
from app.schemas.message import HistoryMessage
from app.utils.datetime import utcnow

logger = logging.getLogger(__name__)
WHATSAPP_REPLY_LIMIT = 4000
INDIA_TIME = timezone(timedelta(hours=5, minutes=30))


class GeminiService:
    def __init__(self, client: genai.Client, settings: Settings) -> None:
        self.client = client
        self.settings = settings

    async def generate(self, history: list[HistoryMessage], instruction: str) -> str:
        contents = map_history(history, self.settings.conversation_history_char_limit)
        if not contents:
            raise GeminiError("gemini_empty_input")
        logger.info("gemini_started")
        try:
            response = await asyncio.wait_for(
                self.client.aio.models.generate_content(
                    model=self.settings.gemini_model,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=instruction
                        + "\nCurrent UTC date: "
                        + utcnow().date().isoformat()
                        + "\nCurrent date in India (IST): "
                        + utcnow().astimezone(INDIA_TIME).date().isoformat()
                        + f"\nFinish the complete reply within {WHATSAPP_REPLY_LIMIT} characters.",
                        tools=[types.Tool(google_search=types.GoogleSearch())],
                        max_output_tokens=8192,
                    ),
                ),
                timeout=self.settings.http_timeout_seconds + 2,
            )
        except errors.APIError as exc:
            raise GeminiError(
                f"gemini_http_{exc.code}", retryable=exc.code in (408, 429, 500, 502, 503, 504)
            ) from None
        except (httpx.TransportError, asyncio.TimeoutError):
            raise GeminiError("gemini_timeout_or_transport", retryable=True) from None
        candidate = response.candidates[0] if response.candidates else None
        if candidate and candidate.finish_reason == types.FinishReason.MAX_TOKENS:
            raise GeminiError("gemini_incomplete_response", retryable=True)
        text = (response.text or "").strip()
        if not text:
            raise GeminiError("gemini_empty_response", retryable=True)
        if len(text.encode("utf-16-le")) // 2 > WHATSAPP_REPLY_LIMIT:
            raise GeminiError("gemini_reply_too_long", retryable=True)
        logger.info("gemini_completed")
        return text
