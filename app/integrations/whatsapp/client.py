import logging
from typing import Any
from uuid import UUID

import httpx

from app.core.config import Settings
from app.integrations.whatsapp.exceptions import MetaAPIError

logger = logging.getLogger(__name__)


class WhatsAppClient:
    def __init__(self, client: httpx.AsyncClient, settings: Settings) -> None:
        self.client = client
        self.settings = settings

    async def send_text(
        self, recipient: str, text: str, message_id: UUID
    ) -> tuple[str, dict[str, Any]]:
        logger.info("meta_send_started", extra={"message_id": message_id})
        try:
            response = await self.client.post(
                f"https://graph.facebook.com/{self.settings.meta_graph_api_version}/"
                f"{self.settings.meta_phone_number_id}/messages",
                headers={
                    "Authorization": "Bearer " + self.settings.meta_access_token.get_secret_value()
                },
                json={
                    "messaging_product": "whatsapp",
                    "recipient_type": "individual",
                    "to": recipient,
                    "type": "text",
                    "text": {"body": text, "preview_url": False},
                    "biz_opaque_callback_data": str(message_id),
                },
            )
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout):
            raise MetaAPIError("meta_connection_failed", retryable=True) from None
        except httpx.TransportError:
            raise MetaAPIError("meta_transport_uncertain", uncertain=True) from None
        if response.status_code >= 500 or response.status_code == 408:
            raise MetaAPIError(f"meta_http_{response.status_code}", uncertain=True)
        if response.is_error:
            code = "unknown"
            try:
                value = response.json().get("error", {}).get("code")
                if isinstance(value, int):
                    code = str(value)
            except (ValueError, AttributeError):
                pass
            raise MetaAPIError(
                f"meta_http_{response.status_code}_code_{code}",
                retryable=response.status_code == 429,
            )
        try:
            payload = response.json()
            provider_id = payload["messages"][0]["id"]
            if not isinstance(provider_id, str) or not provider_id:
                raise ValueError("missing_id")
        except (ValueError, KeyError, IndexError, TypeError):
            raise MetaAPIError("meta_response_uncertain", uncertain=True) from None
        logger.info("meta_send_completed", extra={"message_id": message_id})
        return provider_id, payload
