import json
import time
from pathlib import Path

import pytest
from sqlalchemy import select

from app.core.constants import MessageDirection, MessageStatus, ProcessingJobStatus
from app.models import Message, ProcessingJob

pytestmark = pytest.mark.integration
URL = "/api/v1/webhooks/whatsapp"


def status_payload(message_id, status, correlation=None):
    payload = json.loads(Path("tests/fixtures/whatsapp_status.json").read_text())
    value = payload["entry"][0]["changes"][0]["value"]["statuses"][0]
    value.update(id=message_id, status=status, timestamp=str(int(time.time())))
    if correlation:
        value["biz_opaque_callback_data"] = str(correlation)
    if status == "failed":
        value["errors"] = [{"code": 131026, "title": "not delivered", "message": "private text"}]
    return payload


@pytest.mark.parametrize("status", ["sent", "delivered", "read", "failed"])
async def test_status_updates_same_outbound(api, signed, payload, worker, sessions, status):
    jobs, chatbot, _ = worker
    await api.post(URL, **signed(payload()))
    await jobs.tick()
    async with sessions() as session:
        outbound = (
            await session.scalars(
                select(Message).where(Message.direction == MessageDirection.OUTBOUND)
            )
        ).one()
        outbound_id, provider_id = outbound.id, outbound.whatsapp_message_id
    response = await api.post(URL, **signed(status_payload(provider_id, status)))
    assert response.status_code == 200
    async with sessions() as session:
        message = await session.get(Message, outbound_id)
        assert message.status == MessageStatus(status.upper())
        assert getattr(message, status + "_at") is not None
        if status == "failed":
            assert message.error_code == "131026"
            assert "private text" not in message.error_message
    chatbot.reply.assert_awaited_once()


async def test_receipts_do_not_regress(api, signed, payload, worker, sessions):
    jobs, _, _ = worker
    await api.post(URL, **signed(payload()))
    await jobs.tick()
    async with sessions() as session:
        outbound = (
            await session.scalars(
                select(Message).where(Message.direction == MessageDirection.OUTBOUND)
            )
        ).one()
        mid, provider_id = outbound.id, outbound.whatsapp_message_id
    for status in ("read", "sent", "delivered", "read"):
        await api.post(URL, **signed(status_payload(provider_id, status)))
    async with sessions() as session:
        message = await session.get(Message, mid)
        assert message.status == MessageStatus.READ
        assert message.delivered_at and message.sent_at and message.read_at


@pytest.mark.parametrize("receipt", ["sent", "delivered", "read"])
async def test_status_before_send_response_and_uncertain_reconciliation(
    api, signed, payload, worker, sessions, receipt
):
    jobs, _, whatsapp = worker
    from app.integrations.whatsapp.exceptions import MetaAPIError

    await api.post(URL, **signed(payload()))
    whatsapp.send_text.side_effect = MetaAPIError("timeout", uncertain=True)
    await jobs.tick()
    async with sessions() as session:
        outgoing = (
            await session.scalars(
                select(Message).where(Message.direction == MessageDirection.OUTBOUND)
            )
        ).one()
        mid = outgoing.id
    await api.post(URL, **signed(status_payload("wamid.late", receipt, mid)))
    async with sessions() as session:
        message = await session.get(Message, mid)
        job = (await session.scalars(select(ProcessingJob))).one()
        assert message.whatsapp_message_id == "wamid.late"
        assert message.status == MessageStatus(receipt.upper())
        assert message.error_code is None
        assert job.status == ProcessingJobStatus.COMPLETED


async def test_orphan_receipt_is_reconciled_after_id_exists(api, signed, payload, worker, sessions):
    from app.models import WebhookEvent
    from app.repositories.message_repository import MessageRepository

    await api.post(URL, **signed(status_payload("wamid.orphan", "read")))
    await api.post(URL, **signed(payload()))
    async with sessions() as session, session.begin():
        job = (await session.scalars(select(ProcessingJob))).one()
        inbound = await session.get(Message, job.message_id)
        outbound = await MessageRepository(session).assistant(inbound, "Saved reply")
        outbound.whatsapp_message_id = "wamid.orphan"
        outbound_id = outbound.id
    jobs, chatbot, _ = worker
    await jobs.tick()
    chatbot.reply.assert_not_awaited()
    async with sessions() as session:
        outbound = await session.get(Message, outbound_id)
        assert outbound.status == MessageStatus.READ
        event = (
            await session.scalars(select(WebhookEvent).where(WebhookEvent.event_type == "status"))
        ).one()
        assert event.processed
