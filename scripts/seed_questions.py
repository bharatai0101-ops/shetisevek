"""Seed 20 demo questions; no processing jobs or provider calls are created."""

import asyncio
from datetime import timedelta
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from app.core.config import get_settings
from app.core.constants import MessageDirection, MessageRole, MessageStatus, MessageType
from app.db.session import make_engine, make_sessions
from app.models import Message, User
from app.repositories.conversation_repository import ConversationRepository
from app.utils.datetime import utcnow

QUESTIONS = [
    "How should I irrigate onions during dry weather?",
    "Why are the lower leaves of my tomato plants yellow?",
    "When should I sow wheat after the monsoon?",
    "How can I check whether my soil drains well?",
    "What are the signs of water stress in cotton?",
    "How do I prepare a field for chickpea sowing?",
    "My paddy leaves have brown spots. What should I observe?",
    "How can I reduce weeds around young maize plants?",
    "What information is needed for a soil test?",
    "How should I store harvested onions?",
    "Why are flowers dropping from my chilli plants?",
    "How do I inspect banana plants for pest damage?",
    "What should I consider before installing drip irrigation?",
    "How can I protect vegetable seedlings from heavy rain?",
    "What are low-risk ways to monitor pests in soybean?",
    "How do I choose a suitable tomato variety for my farm?",
    "When should I check the moisture around sugarcane roots?",
    "How can I keep farm records for the next season?",
    "What details should I share about wilting groundnut plants?",
    "How can I find my local agricultural extension officer?",
]


async def main() -> None:
    settings = get_settings()
    if settings.app_env == "production":
        raise SystemExit("Demo seeding is disabled in production")
    engine = make_engine(settings)
    now = utcnow()
    try:
        async with make_sessions(engine)() as session, session.begin():
            for i, question in enumerate(QUESTIONS):
                user_id = uuid5(NAMESPACE_URL, f"shetisevek-demo-user:{i}")
                user = await session.get(User, user_id)
                if user is None:
                    raise SystemExit("Run python -m scripts.seed_users first")
                conversation = await ConversationRepository(session).active(user_id)
                timestamp = now - timedelta(seconds=20 - i)
                await session.execute(
                    insert(Message)
                    .values(
                        id=uuid5(NAMESPACE_URL, f"shetisevek-demo-question:{i}"),
                        conversation_id=conversation.id,
                        user_id=user_id,
                        whatsapp_message_id=f"demo-question-{i:02d}",
                        direction=MessageDirection.INBOUND,
                        role=MessageRole.USER,
                        message_type=MessageType.TEXT,
                        text_content="[Demo] " + question,
                        raw_payload={"demo": True},
                        status=MessageStatus.RECEIVED,
                        provider_timestamp=timestamp,
                        created_at=timestamp,
                    )
                    .on_conflict_do_nothing(index_elements=[Message.id])
                )
            count = await session.scalar(
                select(func.count(Message.id)).where(
                    Message.whatsapp_message_id.like("demo-question-%")
                )
            )
            print(f"Demo questions stored: {count}. No processing jobs or messages sent.")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
