from uuid import UUID

from pydantic import BaseModel, ConfigDict


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    display_name: str | None
