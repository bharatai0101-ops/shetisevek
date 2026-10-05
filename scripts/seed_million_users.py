"""Top up the local development database to one million users with demo records."""

import asyncio

from sqlalchemy import text
from sqlalchemy.engine import make_url

from app.core.config import get_settings
from app.db.session import make_engine

TARGET = 1_000_000


async def main() -> None:
    settings = get_settings()
    url = make_url(settings.database_url.get_secret_value())
    if settings.app_env != "development" or url.host not in {"localhost", "127.0.0.1", "::1"}:
        raise SystemExit("This demo seed is restricted to a local development database")
    engine = make_engine(settings)
    try:
        async with engine.begin() as connection:
            await connection.execute(text("LOCK TABLE users IN SHARE ROW EXCLUSIVE MODE"))
            existing = int(await connection.scalar(text("SELECT count(*) FROM users")) or 0)
            missing = max(0, TARGET - existing)
            last_index = int(
                await connection.scalar(
                    text(
                        "SELECT coalesce(max(substring(whatsapp_user_id from 16)::bigint), 0) "
                        "FROM users WHERE whatsapp_user_id ~ '^demo-million-u-[0-9]+$'"
                    )
                )
                or 0
            )
            print(f"Existing users: {existing:,}. Adding {missing:,} demo users.", flush=True)
            for start in range(last_index + 1, last_index + missing + 1, 50_000):
                end = min(start + 49_999, last_index + missing)
                await connection.execute(
                    text("""
                    INSERT INTO users
                        (id, whatsapp_user_id, phone_number, display_name,
                         first_seen_at, last_seen_at, created_at, updated_at)
                    SELECT md5('shetisevek-demo-million:' || n::text)::uuid,
                           'demo-million-u-' || n::text,
                           '+91 000 ' || lpad(n::text, 7, '0'),
                           'Demo Farmer ' || n::text,
                           now() - interval '90 days', now() - interval '90 days', now(), now()
                    FROM generate_series(CAST(:start AS bigint), CAST(:end AS bigint)) AS n
                """),
                    {"start": start, "end": end},
                )
                print(f"Prepared {existing + end - last_index:,} users.", flush=True)
            total = int(await connection.scalar(text("SELECT count(*) FROM users")) or 0)
            if existing <= TARGET and total != TARGET:
                raise RuntimeError("Unexpected total; rolling back the import")
        print(f"Committed database total: {total:,}. No messaging jobs created.", flush=True)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
