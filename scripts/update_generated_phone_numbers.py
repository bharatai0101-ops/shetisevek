"""Replace zero-prefixed generated phones with stable 70-99 prefixes."""

import asyncio

from sqlalchemy import bindparam, select, update
from sqlalchemy.engine import make_url

from app.core.config import get_settings
from app.db.session import make_engine
from app.models import User
from app.utils.farmer_display import generated_farmer_details


async def main() -> None:
    settings = get_settings()
    url = make_url(settings.database_url.get_secret_value())
    if settings.app_env != "development" or url.host not in {"localhost", "127.0.0.1", "::1"}:
        raise SystemExit("Generated phone updates require a local development database")
    engine = make_engine(settings)
    try:
        async with engine.begin() as conn:
            ids = (
                (
                    await conn.execute(
                        select(User.id).where(
                            User.whatsapp_user_id.like("demo-%"),
                            User.phone_number.like("+91 000%"),
                        )
                    )
                )
                .scalars()
                .all()
            )
            statement = (
                update(User.__table__)
                .where(User.id == bindparam("record_id"))
                .values(phone_number=bindparam("new_phone"))
            )
            for start in range(0, len(ids), 500):
                await conn.execute(
                    statement,
                    [
                        {"record_id": user_id, "new_phone": generated_farmer_details(user_id)[0]}
                        for user_id in ids[start : start + 500]
                    ],
                )
        print(f"Updated {len(ids):,} generated phone numbers. Real-user records preserved.")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
