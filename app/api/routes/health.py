from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import session_dependency
from app.core.exceptions import DatabaseUnavailable

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
async def ready(session: Annotated[AsyncSession, Depends(session_dependency)]) -> dict[str, str]:
    try:
        await session.execute(text("SELECT 1"))
        version = await session.scalar(text("SELECT version_num FROM alembic_version LIMIT 1"))
        if not version:
            raise DatabaseUnavailable()
    except Exception:
        raise DatabaseUnavailable() from None
    return {"status": "ready"}
