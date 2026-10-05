"""Import DOCX demo questions without creating WhatsApp processing jobs."""

import argparse
import asyncio
import re
from datetime import timedelta
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5
from xml.etree import ElementTree
from zipfile import ZipFile

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from app.core.config import get_settings
from app.core.constants import (
    ConversationStatus,
    MessageDirection,
    MessageRole,
    MessageStatus,
    MessageType,
)
from app.db.session import make_engine
from app.models import Conversation, FarmerProfile, Message, User
from app.utils.datetime import utcnow

FIRST_NAMES = [
    "संतोष",
    "सुरेश",
    "रमेश",
    "गणेश",
    "विजय",
    "अशोक",
    "प्रकाश",
    "संजय",
    "दत्तात्रय",
    "विठ्ठल",
    "शंकर",
    "राजेश",
    "सुनील",
    "अनिल",
    "बाळासाहेब",
    "लक्ष्मी",
    "सुनीता",
    "सविता",
    "मंगला",
    "शोभा",
]
LAST_NAMES = [
    "पाटील",
    "जाधव",
    "शिंदे",
    "पवार",
    "देशमुख",
    "कदम",
    "मोरे",
    "चव्हाण",
    "भोसले",
    "गायकवाड",
    "साळुंखे",
    "काळे",
    "वाघ",
    "माने",
    "शेलार",
    "थोरात",
    "निकम",
    "सोनवणे",
    "खेडकर",
    "कुलकर्णी",
]


def read_questions(path: Path) -> list[tuple[int, str, str]]:
    with ZipFile(path) as document:
        root = ElementTree.fromstring(document.read("word/document.xml"))
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    category = "कृषी"
    questions = []
    for paragraph in root.findall(".//w:p", ns):
        text = "".join(t.text or "" for t in paragraph.findall(".//w:t", ns)).strip()
        if text.startswith("विभाग") and ":" in text:
            category = text.split(":", 1)[1].strip()
        match = re.match(r"^(\d+)\.\s+(.+)$", text)
        if match:
            questions.append((int(match[1]), match[2], category))
    if [number for number, _, _ in questions] != list(range(1, 401)):
        raise ValueError("Expected exactly 400 consecutive numbered questions")
    return questions


async def main(path: Path) -> None:
    questions = read_questions(path)
    settings = get_settings()
    if settings.app_env != "development":
        raise SystemExit("Demo import requires APP_ENV=development")
    engine = make_engine(settings)
    now = utcnow()
    inserted = 0
    try:
        async with engine.begin() as connection:
            for number, question, category in questions:
                key = f"shetisevek-docx-demo:{path.name}:{number}"
                user_id = uuid5(NAMESPACE_URL, key + ":user")
                conversation_id = uuid5(NAMESPACE_URL, key + ":conversation")
                name = FIRST_NAMES[(number - 1) % 20] + " " + LAST_NAMES[(number - 1) // 20]
                timestamp = now - timedelta(seconds=400 - number)
                await connection.execute(
                    insert(User)
                    .values(
                        id=user_id,
                        whatsapp_user_id=f"demo-docx-{number:04d}",
                        phone_number=f"+91 00000 {number:05d}",
                        display_name=name,
                        first_seen_at=timestamp,
                        last_seen_at=timestamp,
                    )
                    .on_conflict_do_nothing(index_elements=[User.id])
                )
                await connection.execute(
                    insert(FarmerProfile)
                    .values(
                        id=uuid5(NAMESPACE_URL, key + ":profile"),
                        user_id=user_id,
                        preferred_language="Marathi",
                        state="Maharashtra",
                    )
                    .on_conflict_do_nothing(index_elements=[FarmerProfile.user_id])
                )
                await connection.execute(
                    insert(Conversation)
                    .values(
                        id=conversation_id,
                        user_id=user_id,
                        status=ConversationStatus.CLOSED,
                        started_at=timestamp,
                        last_message_at=timestamp,
                    )
                    .on_conflict_do_nothing(index_elements=[Conversation.id])
                )
                message_id = await connection.scalar(
                    insert(Message)
                    .values(
                        id=uuid5(NAMESPACE_URL, key + ":question"),
                        conversation_id=conversation_id,
                        user_id=user_id,
                        whatsapp_message_id=f"demo-docx-{path.name}-{number:04d}",
                        direction=MessageDirection.INBOUND,
                        role=MessageRole.USER,
                        message_type=MessageType.TEXT,
                        text_content=question,
                        raw_payload={
                            "demo": True,
                            "source": path.name,
                            "question_number": number,
                            "category": category,
                        },
                        status=MessageStatus.RECEIVED,
                        provider_timestamp=timestamp,
                        created_at=timestamp,
                    )
                    .on_conflict_do_nothing(index_elements=[Message.id])
                    .returning(Message.id)
                )
                inserted += message_id is not None
            count = await connection.scalar(
                select(func.count(Message.id)).where(
                    Message.raw_payload["source"].astext == path.name
                )
            )
        print(f"Imported {inserted} new questions; {count} stored for this document.")
        print("Dummy farmers only. No processing jobs or outbound messages created.")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("document", type=Path)
    asyncio.run(main(parser.parse_args().document))
