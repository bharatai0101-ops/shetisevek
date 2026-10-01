from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.crop_repository import CropRepository
from app.repositories.farmer_repository import FarmerRepository
from app.schemas.farmer import CropRead, FarmerContext, FarmerProfileUpdate


class FarmerService:
    def __init__(self, session: AsyncSession) -> None:
        self.profiles = FarmerRepository(session)
        self.crops = CropRepository(session)

    async def context(self, user_id: UUID) -> FarmerContext:
        profile = await self.profiles.ensure(user_id)
        return FarmerContext(
            profile=FarmerProfileUpdate.model_validate(profile, from_attributes=True),
            crops=[
                CropRead.model_validate(crop) for crop in await self.crops.list_for_user(user_id)
            ],
        )

    async def update_explicit(self, user_id: UUID, data: FarmerProfileUpdate) -> None:
        await self.profiles.update(user_id, data)
