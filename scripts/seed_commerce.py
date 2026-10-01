"""Insert deterministic demo records without replacing existing data. Never run in production."""

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy.dialects.postgresql import insert

from app.core.config import get_settings
from app.db.session import make_engine
from app.models.commerce import Deal, DealRedemption, FinanceEntry


def demo_id(key: str) -> UUID:
    return uuid5(NAMESPACE_URL, "shetisevek-demo:" + key)


async def main() -> None:
    settings = get_settings()
    if settings.app_env == "production":
        raise SystemExit("Demo seeding is disabled in production")
    engine = make_engine(settings)
    today = datetime.now(timezone(timedelta(hours=5, minutes=30))).date()
    offers = [
        ("Monsoon Seed Bundle 30% Off", "AgriSeed Co.", "Maharashtra", -20, 20),
        ("Free Soil Test with Fertilizer Pack", "SoilLab India", "Tamil Nadu", -15, 5),
        ("Drip Kit EMI at 0%", "FlowFarm", "Gujarat", -30, 45),
        ("Tractor Tyre Exchange", "MahaAgro Motors", "Punjab", -60, -7),
        ("Cold Storage 2 Months Free", "FreshKeep", "Bihar", 10, 70),
    ]
    try:
        async with engine.begin() as connection:
            for i, (title, partner, region, start, end) in enumerate(offers):
                deal_id = demo_id(f"deal-{i}")
                await connection.execute(
                    insert(Deal)
                    .values(
                        id=deal_id,
                        title=title,
                        partner=partner,
                        company_name=partner,
                        contact_person="Demo Partner Contact",
                        phone="",
                        email=f"partner{i}@example.com",
                        gst_number="",
                        address=f"Demo office, {region}",
                        region=region,
                        start=today + timedelta(days=start),
                        end=today + timedelta(days=end),
                        terms="Sample offer for demonstration. Subject to partner availability.",
                        status="Active",
                    )
                    .on_conflict_do_nothing(index_elements=[Deal.id])
                )
                if start < 0:
                    for j in range(3):
                        await connection.execute(
                            insert(DealRedemption)
                            .values(
                                id=demo_id(f"redemption-{i}-{j}"),
                                deal_id=deal_id,
                                occurred_on=today - timedelta(days=10 + j),
                                quantity=120 + i * 70 + j * 20,
                            )
                            .on_conflict_do_nothing(index_elements=[DealRedemption.id])
                        )
            # Daily ledger rows give real daily/weekly/monthly/yearly aggregates.
            for offset in range(370):
                day = today - timedelta(days=offset)
                entries = [
                    ("revenue", "Advisory services", 12000 + offset % 7 * 750, 0),
                    ("revenue", "Advertising", 3500 + offset % 5 * 300, 0),
                    ("expense", "AI inference", 2300 + offset % 3 * 200, 414),
                    ("expense", "WhatsApp Business API", 1400, 252),
                    ("expense", "Cloud & storage", 800, 144),
                ]
                for kind, category, amount, tax in entries:
                    await connection.execute(
                        insert(FinanceEntry)
                        .values(
                            id=demo_id(f"ledger-{day}-{kind}-{category}"),
                            occurred_on=day,
                            kind=kind,
                            category=category,
                            amount=Decimal(amount),
                            tax=Decimal(tax),
                            paid=True,
                        )
                        .on_conflict_do_nothing(index_elements=[FinanceEntry.id])
                    )
            await connection.execute(
                insert(FinanceEntry)
                .values(
                    id=demo_id("unpaid-partner-payout"),
                    occurred_on=today,
                    kind="payout",
                    category="Demo partner payouts",
                    amount=Decimal(382000),
                    tax=0,
                    paid=False,
                )
                .on_conflict_do_nothing(index_elements=[FinanceEntry.id])
            )
        print(
            "Demo data ready: 5 deals, 12 redemptions and finance entries. "
            "Existing records preserved."
        )
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
