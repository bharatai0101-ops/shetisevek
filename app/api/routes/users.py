from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select

from app.api.routes.commerce import Session, require_admin
from app.core.constants import MessageDirection
from app.models import FarmerProfile, Message, User
from app.utils.datetime import utcnow

router = APIRouter(prefix="/api/v1/admin", dependencies=[Depends(require_admin)])


@router.get("/users")
async def list_users(session: Session) -> dict[str, Any]:
    counts = (
        select(Message.user_id, func.count(Message.id).label("questions"))
        .where(Message.direction == MessageDirection.INBOUND)
        .group_by(Message.user_id)
        .subquery()
    )
    result = await session.execute(
        select(User, FarmerProfile.state, func.coalesce(counts.c.questions, 0))
        .outerjoin(FarmerProfile, FarmerProfile.user_id == User.id)
        .outerjoin(counts, counts.c.user_id == User.id)
        .order_by(User.last_seen_at.desc(), User.first_seen_at.desc(), User.id)
        .limit(1000)
    )
    total = await session.scalar(select(func.count(User.id)))
    active = await session.scalar(
        select(func.count(User.id)).where(User.last_seen_at >= utcnow() - timedelta(days=7))
    )
    return {
        "total": total or 0,
        "active_7d": active or 0,
        "items": [
            {
                "id": user.id,
                "name": user.display_name or "Farmer",
                "phone": user.phone_number
                or (
                    "+" + user.whatsapp_user_id
                    if user.whatsapp_user_id.isdigit()
                    else "Demo / not provided"
                ),
                "state": state or "Not provided",
                "questions": questions,
                "joined": user.first_seen_at.date(),
                "active": True,
            }
            for user, state, questions in result.all()
        ],
    }
