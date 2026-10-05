"""Distribute existing local demo activity across the dashboard's six-week window."""

import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings


async def main() -> None:
    settings = get_settings()
    url = make_url(settings.database_url.get_secret_value())
    if settings.app_env != "development" or url.host not in {"localhost", "127.0.0.1", "::1"}:
        raise SystemExit("Demo history requires a local development database")
    now = datetime.now(timezone(timedelta(hours=5, minutes=30)))
    start = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=41)
    engine = create_async_engine(
        settings.database_url.get_secret_value(),
        connect_args={"command_timeout": 180},
        hide_parameters=True,
    )
    try:
        async with engine.begin() as conn:
            await conn.execute(text("LOCK TABLE users IN SHARE ROW EXCLUSIVE MODE"))
            before = (
                await conn.execute(
                    text("""
                SELECT count(*), count(*) FILTER (
                    WHERE last_seen_at >= now() - interval '7 days') FROM users
            """)
                )
            ).one()
            await conn.execute(
                text("""
                WITH ranked AS (
                    SELECT id, last_seen_at >= now() - interval '7 days' AS active,
                           row_number() OVER (
                               PARTITION BY last_seen_at >= now() - interval '7 days'
                               ORDER BY id) - 1 AS n
                    FROM users WHERE whatsapp_user_id LIKE 'demo-million-u-%'
                ), dated AS (
                    SELECT id, LEAST(now() - interval '1 second',
                        CAST(:start AS timestamptz) + interval '1 day' * (
                            CASE WHEN active THEN 35 + n % 7 ELSE
                                (CASE WHEN n % 100 < 12 THEN 0
                                      WHEN n % 100 < 28 THEN 1
                                      WHEN n % 100 < 48 THEN 2
                                      WHEN n % 100 < 72 THEN 3 ELSE 4 END) * 7
                                + (n / 100) % 7 END
                        ) + interval '1 hour') AS joined
                    FROM ranked
                )
                UPDATE users SET first_seen_at = dated.joined,
                    last_seen_at = GREATEST(users.last_seen_at, dated.joined), updated_at = now()
                FROM dated WHERE users.id = dated.id
            """),
                {"start": start},
            )
            await conn.execute(
                text("""
                WITH dated AS (
                    SELECT id, LEAST(now() - interval '1 second',
                        CAST(:start AS timestamptz) + interval '1 day' *
                        ((CAST(raw_payload->>'question_number' AS integer) - 1) * 42 / 400)
                        + interval '2 hours') AS received
                    FROM messages
                    WHERE raw_payload->>'source' = '400_Shetkari_Prashna_Marathi.docx'
                      AND raw_payload->>'demo' = 'true'
                )
                UPDATE messages SET created_at = dated.received,
                    provider_timestamp = dated.received, updated_at = now()
                FROM dated WHERE messages.id = dated.id
            """),
                {"start": start},
            )
            # Keep each imported demo farmer's registration and conversation timestamps
            # consistent with the newly assigned question date.
            await conn.execute(
                text("""
                UPDATE users SET first_seen_at = messages.created_at,
                    updated_at = now()
                FROM messages WHERE users.id = messages.user_id
                  AND messages.raw_payload->>'source' = '400_Shetkari_Prashna_Marathi.docx'
                  AND messages.raw_payload->>'demo' = 'true'
                  AND users.whatsapp_user_id LIKE 'demo-docx-%'
            """)
            )
            await conn.execute(
                text("""
                UPDATE conversations SET started_at = messages.created_at,
                    last_message_at = messages.created_at, updated_at = now()
                FROM messages WHERE conversations.id = messages.conversation_id
                  AND messages.raw_payload->>'source' = '400_Shetkari_Prashna_Marathi.docx'
                  AND messages.raw_payload->>'demo' = 'true'
            """)
            )
            after = (
                await conn.execute(
                    text("""
                SELECT count(*), count(*) FILTER (
                    WHERE last_seen_at >= now() - interval '7 days') FROM users
            """)
                )
            ).one()
            if before != after:
                raise RuntimeError("User totals changed; rolling back demo history")
        print(f"Demo history updated. Preserved {after[0]:,} users and {after[1]:,} active users.")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
