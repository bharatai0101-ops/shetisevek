import json
from uuid import uuid4

import httpx
import pytest

from app.integrations.whatsapp.client import WhatsAppClient
from app.integrations.whatsapp.exceptions import MetaAPIError


async def test_meta_send(settings):
    message_id = uuid4()

    def handler(request):
        assert request.url.path == "/v23.0/111/messages"
        assert request.headers["authorization"] == "Bearer test-access-token"
        assert json.loads(request.content)["biz_opaque_callback_data"] == str(message_id)
        return httpx.Response(200, json={"messages": [{"id": "wamid.sent"}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        mid, _ = await WhatsAppClient(client, settings).send_text("919000000001", "Hi", message_id)
        assert mid == "wamid.sent"


@pytest.mark.parametrize(
    "status,retryable,uncertain",
    [(400, False, False), (401, False, False), (429, True, False), (500, False, True)],
)
async def test_meta_failure(settings, status, retryable, uncertain):
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                status, json={"error": {"code": 123, "message": "private text"}}
            )
        )
    ) as client:
        with pytest.raises(MetaAPIError) as caught:
            await WhatsAppClient(client, settings).send_text("919000000001", "Hi", uuid4())
        assert caught.value.retryable == retryable
        assert caught.value.uncertain == uncertain
        assert "private text" not in str(caught.value)
