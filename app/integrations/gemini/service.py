import asyncio
import logging

import httpx
from google import genai
from google.genai import errors, types

from app.core.config import Settings
from app.integrations.gemini.exceptions import GeminiError
from app.integrations.gemini.mapper import map_history
from app.schemas.message import HistoryMessage
from app.utils.datetime import utcnow
from app.utils.text import whatsapp_text

logger = logging.getLogger(__name__)


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
                        + utcnow().date().isoformat(),
                        tools=[types.Tool(google_search=types.GoogleSearch())],
                        max_output_tokens=2048,
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
        text = response.text
        if not text or not text.strip():
            raise GeminiError("gemini_empty_response", retryable=True)
        logger.info("gemini_completed")
        return grounded_reply(response, text)


def grounded_reply(response: types.GenerateContentResponse, text: str) -> str:
    """Keep provider-supplied source links intact within WhatsApp's text budget."""
    candidates = response.candidates or []
    metadata = candidates[0].grounding_metadata if candidates else None
    sources: list[str] = []
    seen: set[str] = set()
    if metadata:
        for chunk in metadata.grounding_chunks or []:
            web = chunk.web
            if web and web.uri and web.uri.startswith("https://") and web.uri not in seen:
                line = f"{web.title or 'Source'}: {web.uri}"
                if sum(len(item) + 1 for item in sources) + len(line) > 1500:
                    continue
                sources.append(line)
                seen.add(web.uri)
    if not sources:
        return whatsapp_text(text)
    footer = "\n\nSources (Google Search):\n" + "\n".join(sources)
    return whatsapp_text(text, 4000 - len(footer)) + footer
