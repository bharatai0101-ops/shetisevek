"""Bring the local seven-day active-user count to 50,482 using existing demo users."""

import asyncio

from sqlalchemy import text
from sqlalchemy.engine import make_url

from app.core.config import get_settings
from app.db.session import make_engine

TARGET = 50_482


async def main() -> None:
    settings = get_settings()
    url = make_url(settings.database_url.get_secret_value())
    if settings.app_env != "development" or url.host not in {"localhost", "127.0.0.1", "::1"}:
        raise SystemExit("This demo update requires a local development database")
    engine = make_engine(settings)
    try:
        async with engine.begin() as connection:
            await connection.execute(text("LOCK TABLE users IN SHARE ROW EXCLUSIVE MODE"))
            before = int(
                await connection.scalar(
                    text(
                        "SELECT count(*) FROM users WHERE last_seen_at >= now() - interval '7 days'"
                    )
                )
                or 0
            )
            if before > TARGET:
                raise SystemExit("Active count already exceeds target; no users were changed")
            missing = TARGET - before
            updated = int(
                await connection.scalar(
                    text("""
                        WITH candidates AS (
                            SELECT id FROM users
                            WHERE whatsapp_user_id LIKE 'demo-million-u-%'
                              AND last_seen_at < now() - interval '7 days'
                            ORDER BY id
                            LIMIT :missing
                        ), changed AS (
                            UPDATE users SET last_seen_at = now(), updated_at = now()
                            WHERE id IN (SELECT id FROM candidates)
                            RETURNING id
                        )
                        SELECT count(*) FROM changed
                    """),
                    {"missing": missing},
                )
                or 0
            )
            if updated != missing:
                raise RuntimeError("Insufficient inactive demo users; rolling back")
            after = await connection.scalar(
                text("SELECT count(*) FROM users WHERE last_seen_at >= now() - interval '7 days'")
            )
            assert after == TARGET
        print(f"Active users: {before:,} -> {after:,}. Updated {updated:,} existing demo users.")
        print("Live demo registrations may continue increasing this count.")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
