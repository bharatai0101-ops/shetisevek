"""Store supplied sample questions without enqueuing provider requests."""

import random
from datetime import datetime
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncConnection

from app.core.constants import (
    ConversationStatus,
    MessageDirection,
    MessageRole,
    MessageStatus,
    MessageType,
)
from app.models import Conversation, Message

CATEGORY = "कांदा आणि टोमॅटो बाजारातील दर"
QUESTIONS = [
    "आज लासलगाव बाजारात लाल कांद्याची आवक आणि सरासरी मूल्य काय राहिले?",
    "सोलापूर आणि नगर बाजार समितीत कांद्याला किमान व कमाल मूल्य काय मिळत आहे?",
    "पिंपळगाव बाजारात टोमॅटोच्या पेटीला आज काय दर मिळाला?",
    "टोमॅटोचे दर अचानक घसरण्याची मुख्य कारणे कोणती?",
    "कांद्याचे मूल्य वाढण्यासाठी सध्या बाजारात कोणती परिस्थिती आवश्यक आहे?",
    "साठवणुकीतील कांदा बाजारात विक्रीसाठी आणण्याची योग्य वेळ कोणती?",
    "नाशिक जिल्ह्यात टोमॅटोची आवक वाढल्याने दरावर काय परिणाम झाला?",
    "उन्हाळी कांद्याला आगामी काळात चांगला भाव मिळेल का?",
    "दक्षिण भारतात महाराष्ट्रातील कांद्याला कशी मागणी आहे?",
    "टोमॅटो प्रक्रिया उद्योगांमुळे शेतकर्‍यांना दराची हमी कशी मिळू शकते?",
]


QUESTIONS.extend(
    [
        "कापसाला चालू हंगामात प्रति क्विंटल काय भाव मिळण्याची शक्यता आहे?",
        "सोयाबीनचे दर पाच हजार रुपयांच्या वर कधी जाण्याची शक्यता आहे?",
        "आंतरराष्ट्रीय बाजारात सोयाबीन पेंडीच्या मागणीचा स्थानिक भावावर काय परिणाम होत आहे?",
        "शासकीय कापूस खरेदी केंद्र कधी सुरू होणार?",
        "कापसाची गुणवत्ता भावावर कसा प्रभाव टाकते?",
        "सोयाबीनची विक्री सध्या करावी की साठवणूक करावी?",
        "वायदा बाजारात सोयाबीनचे संकेत काय दर्शवत आहेत?",
        "कापूस आयात-निर्यात धोरणाचा स्थानिक बाजारावर काय परिणाम झाला?",
        "सोयाबीनचे किमान आधारभूत मूल्य काय आहे आणि बाजारात काय दर मिळत आहे?",
        "मणाच्या हिशोबाने कापसाचे दर कसे निश्चित केले जातात?",
        "पुणे आणि मुंबई कृषी उत्पन्न बाजार समितीत हिरव्या मिरचीचे मूल्य काय आहे?",
        "आल्याला सध्या बाजारात चांगला दर का मिळत आहे?",
        "डाळिंबाच्या उत्तम दर्जाच्या मालाला आज सोलापूर बाजारात काय भाव मिळाला?",
        "केळीच्या दरात सातत्याने चढ-उतार का होत आहेत?",
        "कोथिंबीर आणि पालेभाज्यांचे भाव पावसामुळे का वाढतात?",
        "लिंबू आणि संत्रा यांचे नागपूर बाजारातील ताजे दर काय आहेत?",
        "द्राक्ष निर्यातीचा काळ सुरू झाल्यावर स्थानिक बाजारातील दरावर काय परिणाम होईल?",
        "सफरचंद आणि पेरूची आवक वाढल्याने स्थानिक फळांचे भाव घसरले आहेत का?",
        "विषमुक्त भाजीपाल्याला शहरांमध्ये काय अतिरिक्त दर मिळतो?",
        "बटाटा आणि लसणाचे भाव आगामी महिन्यात कसे राहतील?",
    ]
)
CATEGORIES = (
    [CATEGORY] * 10
    + ["कापूस आणि सोयाबीन बाजारातील दर"] * 10
    + ["भाजीपाला व फळबाग बाजारातील दर"] * 10
)


async def add_generated_questions(
    connection: AsyncConnection,
    users: list[tuple[UUID, datetime]],
    *,
    additional: bool = False,
    question_count: int = 1,
) -> int:
    if not users:
        return 0
    conversations = []
    messages = []
    for user_id, timestamp in users:
        question_index = random.randrange(10 if additional else 0, len(QUESTIONS))
        suffix = ":cotton-fruit" if additional else ""
        conversation_id = uuid5(NAMESPACE_URL, f"shetisevek-sample-conversation:{user_id}")
        question_id = uuid5(NAMESPACE_URL, f"shetisevek-sample-question:{user_id}{suffix}")
        conversations.append(
            {
                "id": conversation_id,
                "user_id": user_id,
                "status": ConversationStatus.CLOSED,
                "started_at": timestamp,
                "last_message_at": timestamp,
            }
        )
        messages.append(
            {
                "id": question_id,
                "conversation_id": conversation_id,
                "user_id": user_id,
                "whatsapp_message_id": f"demo-market-question-{user_id}{suffix}",
                "direction": MessageDirection.INBOUND,
                "role": MessageRole.USER,
                "message_type": MessageType.TEXT,
                "text_content": QUESTIONS[question_index],
                "raw_payload": {
                    "demo": True,
                    "category": CATEGORIES[question_index],
                    "batch": "cotton-fruit" if additional else "initial",
                    "source": "generated-user-market-questions",
                },
                "status": MessageStatus.RECEIVED,
                "provider_timestamp": timestamp,
                "created_at": timestamp,
            }
        )
        for offset in range(1, question_count):
            index = (question_index + offset) % len(QUESTIONS)
            messages.append(
                {
                    **messages[-1],
                    "id": uuid5(
                        NAMESPACE_URL,
                        f"shetisevek-sample-question:{user_id}{suffix}:extra:{offset}",
                    ),
                    "whatsapp_message_id": f"demo-market-question-{user_id}{suffix}-{offset}",
                    "text_content": QUESTIONS[index],
                    "raw_payload": {
                        "demo": True,
                        "category": CATEGORIES[index],
                        "batch": "cotton-fruit" if additional else "initial",
                        "source": "generated-user-market-questions",
                    },
                }
            )
    await connection.execute(
        insert(Conversation)
        .values(conversations)
        .on_conflict_do_nothing(index_elements=[Conversation.id])
    )
    result = await connection.execute(
        insert(Message)
        .values(messages)
        .on_conflict_do_nothing(index_elements=[Message.id])
        .returning(Message.id)
    )
    return len(result.all())
