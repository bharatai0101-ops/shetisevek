from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.repositories.farmer_repository import FarmerRepository
from app.repositories.user_repository import UserRepository


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.users = UserRepository(session)
        self.farmers = FarmerRepository(session)

    async def identify(self, whatsapp_id: str, name: str | None) -> User:
        user = await self.users.upsert(whatsapp_id, name)
        await self.farmers.ensure(user.id)
        return user
