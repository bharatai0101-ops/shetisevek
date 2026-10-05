"""Add one supplied market question to generated users with no saved questions."""

import argparse
import asyncio

from sqlalchemy import or_, select
from sqlalchemy.engine import make_url

from app.core.config import get_settings
from app.core.constants import MessageDirection
from app.db.session import make_engine
from app.models import Message, User
from app.services.demo_questions import add_generated_questions


async def main(additional: bool = False) -> None:
    settings = get_settings()
    url = make_url(settings.database_url.get_secret_value())
    if settings.app_env != "development" or url.host not in {"localhost", "127.0.0.1", "::1"}:
        raise SystemExit("Sample questions require a local development database")
    engine = make_engine(settings)
    inserted = 0
    try:
        async with engine.begin() as connection:
            visible = (
                select(User.id)
                .order_by(User.last_seen_at.desc(), User.first_seen_at.desc(), User.id)
                .limit(1000)
            )
            has_question = (
                select(Message.id)
                .where(
                    Message.user_id == User.id,
                    Message.direction == MessageDirection.INBOUND,
                    Message.raw_payload["batch"].astext == "cotton-fruit" if additional else True,
                )
                .exists()
            )
            rows = (
                await connection.execute(
                    select(User.id, User.last_seen_at).where(
                        User.whatsapp_user_id.like("demo-%"),
                        or_(User.whatsapp_user_id.like("demo-live-%"), User.id.in_(visible)),
                        ~has_question,
                    )
                )
            ).all()
            for start in range(0, len(rows), 200):
                inserted += await add_generated_questions(
                    connection,
                    [(row[0], row[1]) for row in rows[start : start + 200]],
                    additional=additional,
                )
        print(f"Saved {inserted:,} Marathi market questions. No outbound jobs created.")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--additional", action="store_true")
    asyncio.run(main(parser.parse_args().additional))
