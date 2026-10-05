from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import aliased

from app.api.routes.commerce import Session, require_admin
from app.core.constants import MessageDirection
from app.models import FarmerProfile, Message, ProcessingJob, User
from app.utils.farmer_display import farmer_name, farmer_phone

router = APIRouter(prefix="/api/v1/admin", dependencies=[Depends(require_admin)])


@router.get("/questions")
async def questions(session: Session) -> dict[str, Any]:
    reply = aliased(Message)
    records = (
        await session.execute(
            select(
                Message,
                User.display_name,
                User.phone_number,
                FarmerProfile.preferred_language,
                reply.text_content,
                reply.whatsapp_message_id,
                ProcessingJob.status,
            )
            .join(User, User.id == Message.user_id)
            .outerjoin(FarmerProfile, FarmerProfile.user_id == User.id)
            .outerjoin(reply, reply.reply_to_id == Message.id)
            .outerjoin(ProcessingJob, ProcessingJob.message_id == Message.id)
            .where(Message.direction == MessageDirection.INBOUND)
            .order_by(Message.sequence.desc())
            .limit(1000)
        )
    ).all()
    india = timezone(timedelta(hours=5, minutes=30))
    midnight = datetime.now(india).replace(hour=0, minute=0, second=0, microsecond=0)
    total = await session.scalar(
        select(func.count(Message.id)).where(Message.direction == MessageDirection.INBOUND)
    )
    today = await session.scalar(
        select(func.count(Message.id)).where(
            Message.direction == MessageDirection.INBOUND, Message.created_at >= midnight
        )
    )
    states = dict(
        (state.value, count)
        for state, count in (
            await session.execute(
                select(ProcessingJob.status, func.count(ProcessingJob.id)).group_by(
                    ProcessingJob.status
                )
            )
        ).all()
    )
    unqueued = await session.scalar(
        select(func.count(Message.id))
        .outerjoin(ProcessingJob, ProcessingJob.message_id == Message.id)
        .where(Message.direction == MessageDirection.INBOUND, ProcessingJob.id.is_(None))
    )
    items = []
    for message, name, phone, language, text, provider_id, job_status in records:
        metadata = message.raw_payload or {}
        state = job_status.value if job_status else "PENDING"
        status = (
            "Answered"
            if provider_id
            else "Failed"
            if state == "FAILED"
            else "In Review"
            if state == "PROCESSING"
            else "Pending"
        )
        items.append(
            {
                "id": str(message.id),
                "farmer": farmer_name(name, message.user_id) if message.user_id else "Farmer",
                "phone": farmer_phone(phone),
                "demo": metadata.get("demo") is True,
                "crop": "Not specified",
                "question": message.text_content
                or f"Received {message.message_type.value.lower()}",
                "category": metadata.get("category") or "WhatsApp",
                "language": language or "Not specified",
                "status": status,
                "time": message.created_at.astimezone(india).isoformat(),
                "reply": text,
            }
        )
    return {
        "items": items,
        "summary": {
            "total": total or 0,
            "today": today or 0,
            "pending": (unqueued or 0)
            + sum(states.get(state, 0) for state in ["PENDING", "RETRY", "PROCESSING"]),
            "completed": states.get("COMPLETED", 0),
            "failed": states.get("FAILED", 0),
        },
    }
