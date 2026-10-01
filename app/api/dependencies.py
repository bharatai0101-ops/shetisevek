from collections.abc import AsyncIterator
from typing import cast

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings


def settings_dependency(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


async def session_dependency(request: Request) -> AsyncIterator[AsyncSession]:
    factory = cast(async_sessionmaker[AsyncSession], request.app.state.sessions)
    async with factory() as session:
        yield session
