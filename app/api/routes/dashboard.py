import asyncio
from datetime import datetime, timedelta, timezone
from time import monotonic
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text

from app.api.routes.commerce import Session, require_admin
from app.models import FarmerProfile, User
from app.models.commerce import Deal, DealRedemption
from app.utils.farmer_display import farmer_name

router = APIRouter(prefix="/api/v1/admin", dependencies=[Depends(require_admin)])
_cache: dict[Any, tuple[float, dict[str, Any]]] = {}
_lock = asyncio.Lock()


@router.get("/dashboard")
async def dashboard(session: Session) -> dict[str, Any]:
    # Coalesce concurrent refreshes; never cache a failed calculation.
    async with _lock:
        cached = _cache.get(session.bind)
        if cached and monotonic() - cached[0] < 30:
            return cached[1]
        result = await build_dashboard(session)
        _cache[session.bind] = (monotonic(), result)
        return result


async def build_dashboard(session: Session) -> dict[str, Any]:
    now = datetime.now(timezone(timedelta(hours=5, minutes=30)))
    today = now.date()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=41)
    total = int(
        await session.scalar(
            text("SELECT coalesce(sum(count), 0) FROM dashboard_daily_counts WHERE kind = 'users'")
        )
        or 0
    )
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
    daily_rows = (
        await session.execute(
            text(
                "SELECT kind, day, count FROM dashboard_daily_counts "
                "WHERE day >= :start AND day <= :today"
            ),
            {"start": start.date(), "today": today},
        )
    ).all()
    user_rows = [(day, count) for kind, day, count in daily_rows if kind == "users"]
    question_rows = [(day, count) for kind, day, count in daily_rows if kind == "questions"]
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
