"""Fill missing fields on existing live generated users and the visible user listing."""

import asyncio
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import make_url

from app.core.config import get_settings
from app.db.session import make_engine, make_sessions
from app.models import FarmerProfile, User
from app.utils.farmer_display import farmer_name, farmer_phone, generated_farmer_details


async def main() -> None:
    settings = get_settings()
    url = make_url(settings.database_url.get_secret_value())
    if settings.app_env != "development" or url.host not in {"localhost", "127.0.0.1", "::1"}:
        raise SystemExit("Generated user updates require a local development database")
    engine = make_engine(settings)
    count = 0
    try:
        async with make_sessions(engine)() as session, session.begin():
            visible_ids = (
                select(User.id)
                .order_by(User.last_seen_at.desc(), User.first_seen_at.desc(), User.id)
                .limit(1000)
            )
            records = (
                await session.scalars(
                    select(User).where(
                        User.whatsapp_user_id.like("demo-%"),
                        or_(User.whatsapp_user_id.like("demo-live-%"), User.id.in_(visible_ids)),
                    )
                )
            ).all()
            for user in records:
                phone, state = generated_farmer_details(user.id)
                user.display_name = farmer_name(user.display_name, user.id)
                if not farmer_phone(user.phone_number) or user.phone_number.startswith("+91 000"):
                    user.phone_number = phone
                await session.execute(
                    insert(FarmerProfile)
                    .values(
                        id=uuid5(NAMESPACE_URL, f"shetisevek-generated-profile:{user.id}"),
                        user_id=user.id,
                        state=state,
                        preferred_language="Marathi",
                    )
                    .on_conflict_do_nothing(index_elements=[FarmerProfile.user_id])
                )
                await session.execute(
                    update(FarmerProfile)
                    .where(
                        FarmerProfile.user_id == user.id,
                        or_(FarmerProfile.state.is_(None), FarmerProfile.state == ""),
                    )
                    .values(state=state)
                )
                count += 1
        print(f"Saved names, phone numbers and states for {count:,} generated user records.")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
