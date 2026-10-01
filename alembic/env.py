import asyncio
import os
from logging.config import fileConfig

from dotenv import load_dotenv
from sqlalchemy import Connection, pool
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context
from app.db.base import Base
from app.models import *  # noqa: F403

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)
load_dotenv()
database_url = os.environ.get("DATABASE_URL", "")
if not database_url.startswith("postgresql+asyncpg://"):
    raise RuntimeError("Set DATABASE_URL to a postgresql+asyncpg connection URL")
target_metadata = Base.metadata


def offline() -> None:
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def online() -> None:
    engine = create_async_engine(database_url, poolclass=pool.NullPool)
    async with engine.connect() as connection:
        await connection.run_sync(run)
    await engine.dispose()


if context.is_offline_mode():
    offline()
else:
    asyncio.run(online())
