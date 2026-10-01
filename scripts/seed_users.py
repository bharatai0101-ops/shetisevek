"""Create 1,000 demo farmers without touching existing real users or sending messages."""

import asyncio
from datetime import timedelta
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from app.core.config import get_settings
from app.db.session import make_engine
from app.models import FarmerProfile, User
from app.utils.datetime import utcnow


async def main() -> None:
    settings = get_settings()
    if settings.app_env == "production":
        raise SystemExit("Demo users are disabled in production")
    engine = make_engine(settings)
    names = [
        "Ramesh Patil",
        "Sunita Yadav",
        "Karthik Rao",
        "Harpreet Singh",
        "Anita Deshmukh",
        "Mohan Reddy",
        "Sanjay Pawar",
        "Meena Shah",
    ]
    states = [
        "Maharashtra",
        "Uttar Pradesh",
        "Tamil Nadu",
        "Punjab",
        "Gujarat",
        "Telangana",
        "Bihar",
        "Karnataka",
    ]
    now = utcnow()
    try:
        async with engine.begin() as conn:
            users = []
            profiles = []
            for i in range(1000):
                user_id = uuid5(NAMESPACE_URL, f"shetisevek-demo-user:{i}")
                users.append(
                    {
                        "id": user_id,
                        "whatsapp_user_id": f"demo-user-{i:04d}",
                        "display_name": f"{names[i % len(names)]} (Demo {i + 1:04d})",
                        "first_seen_at": now - timedelta(seconds=i),
                        "last_seen_at": now - timedelta(days=i % 10),
                    }
                )
                profiles.append(
                    {
                        "id": uuid5(NAMESPACE_URL, f"shetisevek-demo-profile:{i}"),
                        "user_id": user_id,
                        "state": states[i % len(states)],
                        "preferred_language": "Marathi" if i % 2 else "Hindi",
                    }
                )
            await conn.execute(
                insert(User).values(users).on_conflict_do_nothing(index_elements=[User.id])
            )
            await conn.execute(
                insert(FarmerProfile)
                .values(profiles)
                .on_conflict_do_nothing(index_elements=[FarmerProfile.user_id])
            )
            count = await conn.scalar(
                select(func.count(User.id)).where(User.whatsapp_user_id.like("demo-user-%"))
            )
            print(f"Demo users stored: {count}. No messages sent.")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
