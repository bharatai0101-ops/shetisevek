from unittest.mock import AsyncMock, MagicMock

import pytest
from google.genai import errors, types

from app.core.constants import MessageRole, MessageType
from app.integrations.gemini.exceptions import GeminiError
from app.integrations.gemini.mapper import map_history
from app.integrations.gemini.service import GeminiService
from app.schemas.message import HistoryMessage


def history():
    return [
        HistoryMessage(
            role=MessageRole.USER, message_type=MessageType.TEXT, text="Onion is 40 days old"
        ),
        HistoryMessage(
            role=MessageRole.ASSISTANT, message_type=MessageType.TEXT, text="What symptoms?"
        ),
        HistoryMessage(role=MessageRole.USER, message_type=MessageType.TEXT, text="Yellow leaves"),
    ]


def test_mapping_chronology_and_budget():
    contents = map_history(history(), 1000)
    assert [item.role for item in contents] == ["user", "model", "user"]
    assert contents[0].parts[0].text == "Onion is 40 days old"
    assert len(map_history(history(), 13)) == 1


async def test_mocked_gemini_response(settings):
    client = MagicMock()
    client.aio.models.generate_content = AsyncMock(
        return_value=types.GenerateContentResponse(
            candidates=[
                types.Candidate(content=types.Content(parts=[types.Part(text="Helpful reply")]))
            ]
        )
    )
    assert await GeminiService(client, settings).generate(history(), "system") == "Helpful reply"
    assert client.aio.models.generate_content.call_args.kwargs["model"] == "test-model"


@pytest.mark.parametrize("status,retryable", [(429, True), (503, True), (400, False), (403, False)])
async def test_failure_classification(settings, status, retryable):
    client = MagicMock()
    client.aio.models.generate_content = AsyncMock(
        side_effect=errors.APIError(status, {"error": {"message": "secret"}})
    )
    with pytest.raises(GeminiError) as caught:
        await GeminiService(client, settings).generate(history(), "system")
    assert caught.value.retryable == retryable
    assert "secret" not in str(caught.value)


async def test_empty_response(settings):
    client = MagicMock()
    client.aio.models.generate_content = AsyncMock(return_value=types.GenerateContentResponse())
    with pytest.raises(GeminiError, match="empty_response"):
        await GeminiService(client, settings).generate(history(), "system")
