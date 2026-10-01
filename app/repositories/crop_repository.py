from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FarmerCrop
from app.schemas.farmer import CropCreate


class CropRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_user(self, user_id: UUID) -> list[FarmerCrop]:
        return list(
            await self.session.scalars(
                select(FarmerCrop)
                .where(FarmerCrop.user_id == user_id)
                .order_by(FarmerCrop.created_at)
            )
        )

    async def add(self, user_id: UUID, data: CropCreate, source_message_id: UUID) -> FarmerCrop:
        await self.session.execute(
            insert(FarmerCrop)
            .values(user_id=user_id, source_message_id=source_message_id, **data.model_dump())
            .on_conflict_do_nothing(index_elements=[FarmerCrop.source_message_id])
        )
        return (
            await self.session.scalars(
                select(FarmerCrop).where(FarmerCrop.source_message_id == source_message_id)
            )
        ).one()
