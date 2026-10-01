from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FarmerProfile
from app.schemas.farmer import FarmerProfileUpdate


class FarmerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def ensure(self, user_id: UUID) -> FarmerProfile:
        await self.session.execute(
            insert(FarmerProfile).values(user_id=user_id).on_conflict_do_nothing()
        )
        return (
            await self.session.scalars(
                select(FarmerProfile).where(FarmerProfile.user_id == user_id)
            )
        ).one()

    async def update(self, user_id: UUID, data: FarmerProfileUpdate) -> FarmerProfile:
        profile = await self.ensure(user_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(profile, field, value)
        await self.session.flush()
        return profile
