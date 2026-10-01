from typing import Any

from sqlalchemy import String, cast, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Message, WebhookEvent


class WebhookRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(
        self, key: str, kind: str, payload: dict[str, Any], provider_id: str | None = None
    ) -> WebhookEvent | None:
        statement = (
            insert(WebhookEvent)
            .values(
                event_key=key,
                event_type=kind,
                payload=payload,
                provider_message_id=provider_id,
                processed=False,
            )
            .on_conflict_do_nothing(index_elements=[WebhookEvent.event_key])
            .returning(WebhookEvent)
        )
        return (await self.session.scalars(statement)).one_or_none()

    async def pending_statuses(self, provider_id: str) -> list[WebhookEvent]:
        return list(
            await self.session.scalars(
                select(WebhookEvent)
                .where(
                    WebhookEvent.provider_message_id == provider_id,
                    WebhookEvent.event_type == "status",
                    WebhookEvent.processed.is_(False),
                )
                .order_by(WebhookEvent.received_at)
            )
        )

    async def reconcilable(self) -> list[WebhookEvent]:
        # Join only known messages so old unmatchable events cannot starve newer receipts.
        return list(
            await self.session.scalars(
                select(WebhookEvent)
                .join(
                    Message,
                    or_(
                        Message.whatsapp_message_id == WebhookEvent.provider_message_id,
                        cast(Message.id, String)
                        == WebhookEvent.payload["biz_opaque_callback_data"].astext,
                    ),
                )
                .where(WebhookEvent.event_type == "status", WebhookEvent.processed.is_(False))
                .order_by(WebhookEvent.received_at)
                .limit(100)
            )
        )
