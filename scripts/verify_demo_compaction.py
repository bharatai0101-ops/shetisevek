"""Read-only validation of compacted demo storage and administrative display counts."""

import asyncio
import json

import httpx
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import make_engine


async def main() -> None:
    settings = get_settings()
    engine = make_engine(settings)
    try:
        async with engine.connect() as connection:
            # Demo growth can run during validation; compare totals in one snapshot.
            connection = await connection.execution_options(isolation_level="REPEATABLE READ")
            summary = dict(
                (
                    await connection.execute(
                        text("""
                SELECT count(*) FILTER (WHERE direction = 'INBOUND') AS questions,
                       count(*) FILTER (WHERE raw_payload->>'demo' = 'true') AS demo_messages,
                       count(*) FILTER (WHERE (raw_payload->>'demo') IS DISTINCT FROM 'true')
                           AS real_messages
                FROM messages
            """)
                    )
                )
                .mappings()
                .one()
            )
            maximum = await connection.scalar(
                text("""
                SELECT coalesce(max(n), 0) FROM (
                    SELECT count(*) AS n FROM messages m JOIN users u ON u.id = m.user_id
                    WHERE u.whatsapp_user_id LIKE 'demo-%' AND m.direction = 'INBOUND'
                        AND m.raw_payload->>'demo' = 'true'
                    GROUP BY m.user_id
                ) counts
            """)
            )
            assert maximum <= 1, "Multiple sample messages remain for a demo user"
            missing = await connection.scalar(
                text("""
                SELECT count(*) FROM users WHERE whatsapp_user_id LIKE 'demo-%'
                    AND demo_question_count IS NULL
            """)
            )
            assert missing == 0, "Missing saved demo display counts"
            cached = await connection.scalar(
                text("""
                SELECT sum(count) FROM dashboard_daily_counts WHERE kind = 'questions'
            """)
            )
            assert cached == summary["questions"], "Dashboard question counts disagree"
            summary["max_demo_questions_per_user"] = maximum
    finally:
        await engine.dispose()

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.get(
            "http://127.0.0.1:8000/api/v1/admin/users",
            headers={"X-Admin-Token": settings.admin_api_token.get_secret_value()},
        )
        response.raise_for_status()
        listing = response.json()
    demo_counts = [item["questions"] for item in listing["items"] if item["demo"]]
    assert demo_counts and min(demo_counts) >= 11, "Sample UI counts were reduced"
    summary["display_count_min"] = min(demo_counts)
    summary["display_count_max"] = max(demo_counts)
    print(json.dumps(summary))


if __name__ == "__main__":
    asyncio.run(main())
