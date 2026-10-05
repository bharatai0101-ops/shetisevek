from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select

from app.api.routes.commerce import Session, require_admin
from app.core.constants import MessageDirection
from app.models import FarmerProfile, Message, User
from app.models.commerce import Deal, DealRedemption
from app.utils.farmer_display import farmer_name

router = APIRouter(prefix="/api/v1/admin", dependencies=[Depends(require_admin)])


@router.get("/dashboard")
async def dashboard(session: Session) -> dict[str, Any]:
    now = datetime.now(timezone(timedelta(hours=5, minutes=30)))
    today = now.date()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=41)
    total = int(await session.scalar(select(func.count(User.id))) or 0)
    active = int(
        await session.scalar(
            select(func.count(User.id)).where(User.last_seen_at >= now - timedelta(days=7))
        )
        or 0
    )
    profiles = int(
        await session.scalar(
            select(func.count(FarmerProfile.id)).where(
                FarmerProfile.state.is_not(None), FarmerProfile.state != ""
            )
        )
        or 0
    )
    active_deals = int(
        await session.scalar(
            select(func.count(Deal.id)).where(
                Deal.status == "Active", Deal.start <= today, Deal.end >= today
            )
        )
        or 0
    )
    user_day = func.date(func.timezone("Asia/Kolkata", User.first_seen_at))
    message_day = func.date(func.timezone("Asia/Kolkata", Message.created_at))
    user_rows = (
        await session.execute(
            select(user_day, func.count(User.id))
            .where(User.first_seen_at >= start, User.first_seen_at <= now)
            .group_by(user_day)
        )
    ).all()
    question_rows = (
        await session.execute(
            select(message_day, func.count(Message.id))
            .where(
                Message.created_at >= start,
                Message.created_at <= now,
                Message.direction == MessageDirection.INBOUND,
            )
            .group_by(message_day)
        )
    ).all()
    redemption_rows = (
        await session.execute(
            select(DealRedemption.occurred_on, func.sum(DealRedemption.quantity))
            .where(DealRedemption.occurred_on >= start.date(), DealRedemption.occurred_on <= today)
            .group_by(DealRedemption.occurred_on)
        )
    ).all()
    users_by_day = {day: count for day, count in user_rows}
    questions_by_day = {day: count for day, count in question_rows}
    redeemed_by_day = {day: count for day, count in redemption_rows}
    series = []
    for offset in range(42):
        day = start.date() + timedelta(days=offset)
        series.append(
            {
                "date": day.isoformat(),
                "label": day.strftime("%d %b"),
                "new_users": users_by_day.get(day, 0),
                "questions": questions_by_day.get(day, 0),
                "redemptions": int(redeemed_by_day.get(day, 0)),
            }
        )
    weekly = []
    for index in range(6):
        days = series[index * 7 : (index + 1) * 7]
        weekly.append(
            {
                "label": f"W{index + 1}",
                "start": days[0]["date"],
                "end": days[-1]["date"],
                "new_users": sum(day["new_users"] for day in days),
                "questions": sum(day["questions"] for day in days),
            }
        )
    series = series[-30:]
    recent = (
        await session.execute(
            select(User, FarmerProfile.state)
            .outerjoin(FarmerProfile, FarmerProfile.user_id == User.id)
            .order_by(User.first_seen_at.desc(), User.id)
            .limit(4)
        )
    ).all()
    return {
        "updated_at": now.isoformat(),
        "summary": {
            "total_users": total,
            "active_deals": active_deals,
            "active_7d": active,
            "profiles_with_state": profiles,
            "questions_30d": sum(day["questions"] for day in series),
            "redemptions_30d": sum(day["redemptions"] for day in series),
        },
        "series": series,
        "growth_weekly": weekly,
        "recent_users": [
            {
                "id": str(user.id),
                "name": farmer_name(user.display_name, user.id),
                "state": state or "Not provided",
                "joined": user.first_seen_at.isoformat(),
            }
            for user, state in recent
        ],
    }
