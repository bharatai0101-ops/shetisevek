from uuid import UUID

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.utils.datetime import utcnow


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert(self, whatsapp_id: str, name: str | None) -> User:
        statement = insert(User).values(
            whatsapp_user_id=whatsapp_id,
            display_name=name,
            first_seen_at=utcnow(),
            last_seen_at=utcnow(),
        )
        returning = statement.on_conflict_do_update(
            index_elements=[User.whatsapp_user_id],
            set_={
                "last_seen_at": utcnow(),
                "updated_at": utcnow(),
                "display_name": func.coalesce(statement.excluded.display_name, User.display_name),
            },
        ).returning(User)
        return (await self.session.scalars(returning)).one()

    async def get(self, user_id: UUID) -> User:
        user = await self.session.get(User, user_id)
        if user is None:
            raise LookupError("user_missing")
        return user
