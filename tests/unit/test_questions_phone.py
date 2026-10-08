from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from app.api.routes.questions import questions
from app.utils.datetime import utcnow


@pytest.mark.parametrize(
    "phone,whatsapp_id,expected",
    [
        (None, "919000000001", "+919000000001"),
        ("", "919000000001", "+919000000001"),
        ("+91 90000 00001", "919000000001", "+91 90000 00001"),
        (None, "demo-farmer-1", None),
        ("Demo 1", "demo-farmer-1", None),
    ],
)
async def test_questions_returns_saved_phone_or_whatsapp_sender(phone, whatsapp_id, expected):
    message = SimpleNamespace(
        id=uuid4(), user_id=uuid4(), raw_payload={}, text_content="Test question",
        created_at=utcnow(),
    )
    records = Mock()
    records.all.return_value = [
        (message, "Test Farmer", phone, whatsapp_id, None, None, None, None)
    ]
    states = Mock()
    states.all.return_value = []
    session = AsyncMock()
    session.execute.side_effect = [records, states]
    session.scalar.side_effect = [1, 1, 0]

    result = await questions(session)

    assert result["items"][0]["phone"] == expected
