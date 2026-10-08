"""Persist explicitly enabled demo growth without creating messaging jobs."""

import asyncio
import logging
import random
import time
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import Settings
from app.models import FarmerProfile, User
from app.services.demo_questions import add_generated_questions
from app.utils.datetime import utcnow
from app.utils.farmer_display import (
    demo_display_question_count,
    farmer_name,
    generated_farmer_details,
)

logger = logging.getLogger(__name__)


async def run_demo_user_growth(engine: AsyncEngine, settings: Settings) -> None:
    if not settings.demo_user_growth_enabled:
        return
    logger.info("demo_user_growth_started")
    while True:
        await asyncio.sleep(15)
        tick = int(time.time())
        now = utcnow()
        count = random.randint(1, 2)
        try:
            async with engine.begin() as connection:
                # A shared tick lock and unique IDs prevent overlapping API instances
                # from inserting more than two demo users in the same second.
                locked = await connection.scalar(
                    text("SELECT pg_try_advisory_xact_lock(:tick)"), {"tick": tick}
                )
                if not locked:
                    continue
                users = []
                profiles = []
                question_users = []
                for index in range(1, count + 1):
                    user_id = uuid5(NAMESPACE_URL, f"shetisevek-live-demo:{tick}:{index}")
                    phone, state = generated_farmer_details(user_id)
                    question_users.append((user_id, now))
                    users.append(
                        {
                            "id": user_id,
                            "whatsapp_user_id": f"demo-live-{tick}-{index}",
                            "phone_number": phone,
                            "display_name": farmer_name(f"Demo Farmer {tick}-{index}", user_id),
                            "demo_question_count": demo_display_question_count(user_id),
                            "first_seen_at": now,
                            "last_seen_at": now,
                        }
                    )
                    profiles.append(
                        {
                            "id": uuid5(NAMESPACE_URL, f"shetisevek-live-profile:{tick}:{index}"),
                            "user_id": user_id,
                            "state": state,
                            "preferred_language": "Marathi",
                        }
                    )
                await connection.execute(
                    insert(User).values(users).on_conflict_do_nothing(index_elements=[User.id])
                )
                await connection.execute(
                    insert(FarmerProfile)
                    .values(profiles)
                    .on_conflict_do_nothing(index_elements=[FarmerProfile.user_id])
                )
                await add_generated_questions(connection, question_users)
        except Exception:
            logger.error("demo_user_growth_tick_failed")
