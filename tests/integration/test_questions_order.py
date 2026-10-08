from datetime import timedelta

import pytest
from sqlalchemy import select

from app.api.routes.questions import questions
from app.core.constants import MessageDirection
from app.models import Message
from app.utils.datetime import utcnow

pytestmark = pytest.mark.integration


async def test_questions_orders_by_received_time_not_backfill_insertion(
    api, signed, payload, sessions
):
    url = "/api/v1/webhooks/whatsapp"
    assert (
        await api.post(url, **signed(payload("wamid.latest", "Latest question")))
    ).status_code == 200
    assert (
        await api.post(url, **signed(payload("wamid.backfill", "Older question")))
    ).status_code == 200
    async with sessions() as session, session.begin():
        older = await session.scalar(
            select(Message).where(Message.whatsapp_message_id == "wamid.backfill")
        )
        older.created_at = utcnow() - timedelta(days=1)

    async with sessions() as session:
        result = await questions(session)
        assert [item["question"] for item in result["items"]] == [
            "Latest question",
            "Older question",
        ]
        messages = list(
            await session.scalars(
                select(Message)
                .where(Message.direction == MessageDirection.INBOUND)
                .order_by(Message.sequence)
            )
        )
        assert messages[0].text_content == "Latest question"
