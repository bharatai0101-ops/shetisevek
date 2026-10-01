from google import genai
from google.genai import types

from app.core.config import Settings


def create_gemini_client(settings: Settings) -> genai.Client:
    return genai.Client(
        api_key=settings.gemini_api_key.get_secret_value(),
        http_options=types.HttpOptions(
            timeout=int(settings.http_timeout_seconds * 1000),
            retry_options=types.HttpRetryOptions(attempts=1),
        ),
    )
