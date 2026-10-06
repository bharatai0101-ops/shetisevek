import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import SecretStr

from app.services.demo_user_growth import run_demo_user_growth


async def test_disabled_growth_never_accesses_database(settings):
    engine = MagicMock()
    await run_demo_user_growth(engine, settings)
    engine.begin.assert_not_called()


async def test_enabled_production_growth_with_docker_database(settings):
    config = settings.model_copy(update={"app_env": "production", "demo_user_growth_enabled": True})
    config.database_url = SecretStr("postgresql+asyncpg://test:test@postgres/shetisevek")
    connection = AsyncMock()
    connection.scalar.return_value = True
    engine = MagicMock()
    engine.begin.return_value.__aenter__ = AsyncMock(return_value=connection)
    engine.begin.return_value.__aexit__ = AsyncMock(return_value=False)
    with (
        patch(
            "app.services.demo_user_growth.asyncio.sleep",
            side_effect=[None, asyncio.CancelledError()],
        ),
        patch("app.services.demo_user_growth.random.randint", return_value=1),
        patch(
            "app.services.demo_user_growth.add_generated_questions", new_callable=AsyncMock
        ) as questions,
    ):
        with pytest.raises(asyncio.CancelledError):
            await run_demo_user_growth(engine, config)
    assert connection.execute.await_count == 2
    questions.assert_awaited_once()
    assert questions.call_args.kwargs["question_count"] == 11
