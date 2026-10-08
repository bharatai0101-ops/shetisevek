from unittest.mock import AsyncMock, Mock
from uuid import UUID

import pytest

from app.services.demo_questions import add_generated_questions
from app.utils.datetime import utcnow
from app.utils.farmer_display import demo_display_question_count


def test_demo_display_count_preserves_existing_ui_and_higher_saved_counts():
    user_id = UUID("00000000-0000-0000-0000-000000000005")
    assert demo_display_question_count(user_id, actual=1) == 16
    assert demo_display_question_count(user_id, actual=1, saved=45) == 45
    assert demo_display_question_count(user_id, actual=50, saved=45) == 50


@pytest.mark.parametrize("additional", [False, True])
async def test_generator_stores_only_one_sample_per_new_user(additional):
    user_id = UUID("00000000-0000-0000-0000-000000000005")
    connection = AsyncMock()
    connection.scalars.return_value = []
    result = Mock()
    result.all.return_value = [(user_id,)]
    connection.execute.return_value = result
    assert (
        await add_generated_questions(connection, [(user_id, utcnow())], additional=additional) == 1
    )
    values = connection.execute.call_args_list[-1].args[0].compile().params
    assert values["user_id_m0"] == user_id
    assert values["raw_payload_m0"]["demo"] is True
    assert not any(key.endswith("_m1") for key in values)


async def test_generator_does_not_add_another_sample_for_existing_user():
    user_id = UUID("00000000-0000-0000-0000-000000000005")
    connection = AsyncMock()
    connection.scalars.return_value = [user_id]
    assert await add_generated_questions(connection, [(user_id, utcnow())], additional=True) == 0
    connection.execute.assert_not_called()
