from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.commerce import Deal, DealRedemption, FinanceEntry


def month_shift(day: date, months: int) -> date:
    index = day.year * 12 + day.month - 1 + months
    return date(index // 12, index % 12 + 1, 1)


def deal_status(deal: Deal, today: date) -> str:
    if deal.status != "Active":
        return deal.status
    if deal.end < today:
        return "Expired"
    if deal.start > today:
        return "Scheduled"
    if deal.end <= today + timedelta(days=7):
        return "Expiring"
    return "Active"


async def deal_listing(session: AsyncSession, today: date) -> dict[str, Any]:
    deals = list(await session.scalars(select(Deal).order_by(Deal.created_at.desc(), Deal.id)))
    redemption_rows = (
        await session.execute(
            select(DealRedemption.deal_id, func.sum(DealRedemption.quantity)).group_by(
                DealRedemption.deal_id
            )
        )
    ).all()
    counts = {deal_id: count for deal_id, count in redemption_rows}
    recent = await session.scalar(
        select(func.coalesce(func.sum(DealRedemption.quantity), 0)).where(
            DealRedemption.occurred_on >= today - timedelta(days=29),
            DealRedemption.occurred_on <= today,
        )
    )
    payouts = await session.scalar(
        select(func.coalesce(func.sum(FinanceEntry.amount + FinanceEntry.tax), 0)).where(
            FinanceEntry.kind == "payout", FinanceEntry.paid.is_(False)
        )
    )
    rows = []
    for deal in deals:
        row = {column.name: getattr(deal, column.name) for column in Deal.__table__.columns}
        row.update(
            status=deal_status(deal, today),
            configured_status=deal.status,
            redeemed=int(counts.get(deal.id, 0)),
        )
        rows.append(row)
    return {
        "items": rows,
        "regions": sorted({deal.region for deal in deals}),
        "summary": {
            "active": sum(deal_status(d, today) in ("Active", "Expiring") for d in deals),
            "redemptions_30d": int(recent or 0),
            "expiring": sum(deal_status(d, today) == "Expiring" for d in deals),
            "payouts_due": float(payouts or 0),
        },
    }


async def finance_report(session: AsyncSession, today: date) -> dict[str, Any]:
    # Bound reporting to the five calendar years displayed by the dashboard.
    entries = list(
        await session.scalars(
            select(FinanceEntry).where(
                FinanceEntry.occurred_on >= date(today.year - 4, 1, 1),
                FinanceEntry.occurred_on <= today,
                FinanceEntry.kind.in_(["revenue", "expense"]),
            )
        )
    )
    month_start = today.replace(day=1)
    current = [e for e in entries if e.occurred_on >= month_start]
    revenue = sum((e.amount for e in current if e.kind == "revenue"), Decimal(0))
    expense = sum((e.amount + e.tax for e in current if e.kind == "expense"), Decimal(0))
    ad_income = sum(
        (e.amount for e in current if e.kind == "revenue" and e.category == "Advertising"),
        Decimal(0),
    )

    def bucket(start: date, end: date, label: str) -> dict[str, Any]:
        rows = [e for e in entries if start <= e.occurred_on <= end]
        return {
            "label": label,
            "revenue": float(sum((e.amount for e in rows if e.kind == "revenue"), Decimal(0))),
            "expenses": float(
                sum((e.amount + e.tax for e in rows if e.kind == "expense"), Decimal(0))
            ),
        }

    daily = [
        bucket(
            today - timedelta(days=i),
            today - timedelta(days=i),
            (today - timedelta(days=i)).strftime("%d %b"),
        )
        for i in reversed(range(7))
    ]
    monday = today - timedelta(days=today.weekday())
    weekly = [
        bucket(
            monday - timedelta(weeks=i),
            monday - timedelta(weeks=i) + timedelta(days=6),
            (monday - timedelta(weeks=i)).strftime("%d %b"),
        )
        for i in reversed(range(8))
    ]
    monthly = []
    for i in reversed(range(12)):
        start = month_shift(month_start, -i)
        monthly.append(
            bucket(
                start,
                start.replace(day=monthrange(start.year, start.month)[1]),
                start.strftime("%b %Y"),
            )
        )
    yearly = [
        bucket(date(year, 1, 1), date(year, 12, 31), str(year))
        for year in range(today.year - 4, today.year + 1)
    ]
    expenses = []
    for category in sorted({e.category for e in current if e.kind == "expense"}):
        rows = [e for e in current if e.kind == "expense" and e.category == category]
        amount = sum((e.amount for e in rows), Decimal(0))
        tax = sum((e.tax for e in rows), Decimal(0))
        expenses.append(
            {
                "head": category,
                "amount": float(amount),
                "tax": float(tax),
                "share": float((amount + tax) / expense * 100) if expense else 0,
            }
        )
    return {
        "as_of": today,
        "summary": {
            "revenue": float(revenue),
            "ad_income": float(ad_income),
            "expenses": float(expense),
            "net_margin": float((revenue - expense) / revenue * 100) if revenue else 0,
        },
        "series": {"daily": daily, "weekly": weekly, "monthly": monthly, "yearly": yearly},
        "expenses": expenses,
    }
