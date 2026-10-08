from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from app.api.routes.questions import questions
from app.utils.datetime import utcnow


@pytest.mark.parametrize(
    "owners,expected",
    [
        ([], []),
        (["A", "A", "A"], ["A0", "A1", "A2"]),
        (["A", "A", "B", "B", "C", "C"], ["A0", "B2", "C4", "A1", "B3", "C5"]),
        (["A", "A", "A", "B"], ["A0", "B3", "A1", "A2"]),
        (["A", "B", "C"], ["A0", "B1", "C2"]),
    ],
)
async def test_question_list_rotates_users_without_losing_messages(owners, expected):
    user_ids = {owner: uuid4() for owner in owners}
    rows = []
    for index, owner in enumerate(owners):
        message = SimpleNamespace(
            id=uuid4(),
            user_id=user_ids[owner],
            raw_payload={},
            text_content=f"{owner}{index}",
            created_at=utcnow(),
        )
        # Identical names must not merge distinct users into one queue.
        rows.append((message, "Same name", None, "919000000001", None, None, None, None))
    records = Mock()
    records.all.return_value = rows
    states = Mock()
    states.all.return_value = []
    session = AsyncMock()
    session.execute.side_effect = [records, states]
    session.scalar.side_effect = [len(rows), len(rows), 0]

    result = await questions(session)

    assert [item["question"] for item in result["items"]] == expected
    assert len({item["id"] for item in result["items"]}) == len(rows)
