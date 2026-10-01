from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.crop_repository import CropRepository
from app.schemas.farmer import CropCreate, CropRead


class CropService:
    def __init__(self, session: AsyncSession) -> None:
        self.crops = CropRepository(session)

    async def add_explicit(
        self, user_id: UUID, data: CropCreate, source_message_id: UUID
    ) -> CropRead:
        return CropRead.model_validate(await self.crops.add(user_id, data, source_message_id))
