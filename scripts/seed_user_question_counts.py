"""Top up every existing local user's saved inbound questions to at least eleven."""

import argparse
import asyncio
import json

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings
from app.services.demo_questions import QUESTIONS


async def main(visible_only: bool = False, below_minimum: bool = False) -> None:
    settings = get_settings()
    url = make_url(settings.database_url.get_secret_value())
    if settings.app_env != "development" or url.host not in {"localhost", "127.0.0.1", "::1"}:
        raise SystemExit("Sample questions require a local development database")
    engine = create_async_engine(
        settings.database_url.get_secret_value(),
        connect_args={"command_timeout": 300},
        hide_parameters=True,
    )
    inserted = 0
    checked = 0
    cursor = "00000000-0000-0000-0000-000000000000"
    try:
        async with engine.connect() as conn:
            upper = await conn.scalar(text("SELECT max(id::text) FROM users"))
            await conn.commit()
            if upper is None:
                return
            while True:
                async with conn.begin():
                    rows = (
                        await conn.execute(
                            text("""
                        SELECT id, last_seen_at FROM users
                        WHERE id > CAST(:cursor AS uuid) AND id <= CAST(:upper AS uuid)
                          AND (:visible_only = false OR id IN (
                              SELECT id FROM users
                              ORDER BY last_seen_at DESC, first_seen_at DESC, id LIMIT 1000
                          ))
                          AND (:below_minimum = false OR (
                              SELECT count(*) FROM messages
                              WHERE user_id = users.id AND direction = 'INBOUND'
                          ) < 11)
                        ORDER BY id LIMIT 2000
                    """),
                            {
                                "cursor": cursor,
                                "upper": upper,
                                "visible_only": visible_only,
                                "below_minimum": below_minimum,
                            },
                        )
                    ).all()
                    if not rows:
                        break
                    end = str(rows[-1].id)
                    params = {
                        "user_ids": [row.id for row in rows],
                        "questions": json.dumps(QUESTIONS),
                    }
                    await conn.execute(
                        text("""
                        INSERT INTO conversations
                            (id, user_id, status, started_at, last_message_at)
                        SELECT md5('demo-eleven-conversation:' || id::text)::uuid,
                               id, 'CLOSED', last_seen_at, last_seen_at
                        FROM users WHERE id = ANY(CAST(:user_ids AS uuid[]))
                        ON CONFLICT (id) DO NOTHING
                    """),
                        params,
                    )
                    added = await conn.scalar(
                        text("""
                        WITH counts AS (
                            SELECT u.id, u.last_seen_at, count(m.id)::int AS total
                            FROM users u LEFT JOIN messages m
                                ON m.user_id = u.id AND m.direction = 'INBOUND'
                            WHERE u.id = ANY(CAST(:user_ids AS uuid[]))
                            GROUP BY u.id
                        ), added AS (
                            INSERT INTO messages
                                (id, conversation_id, user_id, direction, role, message_type,
                                 text_content, raw_payload, status, provider_timestamp, created_at)
                            SELECT md5('demo-eleven-question:' || c.id::text || ':' || n)::uuid,
                                   md5('demo-eleven-conversation:' || c.id::text)::uuid,
                                   c.id, 'INBOUND', 'USER', 'TEXT',
                                   CAST(:questions AS jsonb)->>((n - 1) % 30),
                                   jsonb_build_object('demo', true,
                                       'source', 'minimum-eleven-questions', 'slot', n),
                                   'RECEIVED', c.last_seen_at, c.last_seen_at
                            FROM counts c CROSS JOIN LATERAL generate_series(c.total + 1, 11) n
                            ON CONFLICT (id) DO NOTHING RETURNING id
                        ) SELECT count(*) FROM added
                    """),
                        params,
                    )
                inserted += int(added or 0)
                checked += len(rows)
                cursor = end
                print(
                    f"Checked {checked:,} users; saved {inserted:,} sample questions.", flush=True
                )
            remaining = await conn.scalar(
                text("""
                SELECT count(*) FROM (
                    SELECT u.id FROM users u LEFT JOIN messages m
                        ON m.user_id = u.id AND m.direction = 'INBOUND'
                    WHERE u.id <= CAST(:upper AS uuid)
                      AND (:visible_only = false OR u.id IN (
                          SELECT id FROM users
                          ORDER BY last_seen_at DESC, first_seen_at DESC, id LIMIT 1000
                      ))
                    GROUP BY u.id HAVING count(m.id) < 11
                ) deficient
            """),
                {"upper": upper, "visible_only": visible_only},
            )
            print(
                f"Finished: {remaining:,} users below eleven questions. No jobs created.",
                flush=True,
            )
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--visible-only", action="store_true")
    parser.add_argument("--below-minimum", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args.visible_only, args.below_minimum))
