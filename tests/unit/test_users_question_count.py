from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import UUID

import pytest

from app.api.routes.users import list_users
from app.utils.datetime import utcnow


@pytest.mark.parametrize(
    "whatsapp_id,saved,actual,expected",
    [("demo-test", 45, 1, 45), ("demo-test", None, 1, 16), ("919000000001", 45, 3, 3)],
)
async def test_user_listing_keeps_demo_display_count_and_real_actual_count(
    whatsapp_id, saved, actual, expected
):
    user = SimpleNamespace(
        id=UUID("00000000-0000-0000-0000-000000000005"),
        whatsapp_user_id=whatsapp_id,
        phone_number=None,
        display_name="Test Farmer",
        demo_question_count=saved,
        first_seen_at=utcnow(),
    )
    records = Mock()
    records.all.return_value = [(user, "Maharashtra", actual)]
    session = AsyncMock()
    session.execute.return_value = records
    session.scalar.side_effect = [1, 1]

    result = await list_users(session)

    assert result["items"][0]["questions"] == expected
