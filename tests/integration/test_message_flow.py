from datetime import timedelta

import pytest
from sqlalchemy import func, select, update

from app.core.constants import MessageDirection, ProcessingJobStatus
from app.integrations.gemini.exceptions import GeminiError
from app.integrations.whatsapp.exceptions import MetaAPIError
from app.models import FarmerCrop, FarmerProfile, Message, ProcessingJob
from app.utils.datetime import utcnow

pytestmark = pytest.mark.integration
URL = "/api/v1/webhooks/whatsapp"


async def test_daily_memory_keeps_name_beyond_twenty_messages(api, signed, payload, sessions):
    from app.services.conversation_service import ConversationService

    await api.post(URL, **signed(payload("wamid.old", "old name")))
    await api.post(URL, **signed(payload("wamid.name", "majh nav sharad yy")))
    for index in range(22):
        await api.post(URL, **signed(payload(f"wamid.turn.{index}", "tomato question")))
    await api.post(URL, **signed(payload("wamid.recall", "majh nav ky yy")))
    async with sessions() as session, session.begin():
        old = (
            await session.scalars(select(Message).where(Message.whatsapp_message_id == "wamid.old"))
        ).one()
        old.created_at = utcnow() - timedelta(hours=25)
        await session.flush()
        inbound = (
            await session.scalars(
                select(Message).where(Message.whatsapp_message_id == "wamid.recall")
            )
        ).one()
        history = await ConversationService(session).history(inbound)
        assert len(history) == 24
        assert history[0].text == "majh nav sharad yy"
        assert history[-1].text == "majh nav ky yy"
        assert not any(item.text == "old name" for item in history)


async def test_marathi_context_and_outbound_id(api, signed, payload, worker, sessions):
    jobs, chatbot, _ = worker
    await api.post(URL, **signed(payload()))
    assert await jobs.tick()
    await api.post(URL, **signed(payload("wamid.in.2", "पीक 45 दिवसांचे आहे")))
    assert await jobs.tick()
    history = chatbot.reply.call_args.args[0]
    assert "कांद्याची" in history[0].text
    assert "45" in history[-1].text
    assert len(history) == 3
    async with sessions() as session:
        outgoing = list(
            await session.scalars(
                select(Message).where(Message.direction == MessageDirection.OUTBOUND)
            )
        )
        assert len(outgoing) == 2
        assert all(message.whatsapp_message_id for message in outgoing)
        assert all(
            job.status == ProcessingJobStatus.COMPLETED
            for job in await session.scalars(select(ProcessingJob))
        )


async def test_meta_retry_reuses_saved_answer(api, signed, payload, worker, sessions):
    jobs, chatbot, whatsapp = worker
    await api.post(URL, **signed(payload()))
    whatsapp.send_text.side_effect = MetaAPIError("rate_limit", retryable=True)
    assert await jobs.tick()
    async with sessions() as session, session.begin():
        job = (await session.scalars(select(ProcessingJob))).one()
        assert job.status == ProcessingJobStatus.RETRY
        job.available_at = utcnow() - timedelta(seconds=1)
        assert await session.scalar(select(func.count()).select_from(Message)) == 2
    whatsapp.send_text.side_effect = None
    whatsapp.send_text.return_value = ("wamid.success", {"messages": [{"id": "wamid.success"}]})
    assert await jobs.tick()
    chatbot.reply.assert_awaited_once()
    assert whatsapp.send_text.await_count == 2


async def test_gemini_failure_is_durable_and_bounded(api, signed, payload, worker, sessions):
    jobs, chatbot, whatsapp = worker
    await api.post(URL, **signed(payload()))
    chatbot.reply.side_effect = GeminiError("unavailable", retryable=True)
    for _attempt in range(5):
        async with sessions() as session, session.begin():
            await session.execute(
                update(ProcessingJob).values(available_at=utcnow() - timedelta(seconds=1))
            )
        assert await jobs.tick()
    async with sessions() as session:
        job = (await session.scalars(select(ProcessingJob))).one()
        assert job.status == ProcessingJobStatus.FAILED
        assert job.attempts == 5
        assert await session.scalar(select(func.count()).select_from(Message)) == 1
    whatsapp.send_text.assert_not_awaited()
    assert not await jobs.tick()


async def test_uncertain_send_blocks_followups(api, signed, payload, worker, sessions):
    jobs, chatbot, whatsapp = worker
    await api.post(URL, **signed(payload()))
    whatsapp.send_text.side_effect = MetaAPIError("timeout", uncertain=True)
    assert await jobs.tick()
    await api.post(URL, **signed(payload("wamid.in.2", "hello again")))
    assert not await jobs.tick()
    async with sessions() as session:
        job = (
            await session.scalars(select(ProcessingJob).order_by(ProcessingJob.message_sequence))
        ).first()
        assert job.last_error == "delivery_uncertain"
    chatbot.reply.assert_awaited_once()


async def test_stale_generation_job_is_reclaimed(api, signed, payload, worker, sessions):
    await api.post(URL, **signed(payload()))
    async with sessions() as session, session.begin():
        job = (await session.scalars(select(ProcessingJob))).one()
        job.status = ProcessingJobStatus.PROCESSING
        job.locked_at = utcnow() - timedelta(minutes=10)
        job.locked_by = "crashed-worker"
    jobs, chatbot, _ = worker
    assert await jobs.tick()
    chatbot.reply.assert_awaited_once()


async def test_explicit_profile_and_multiple_crops(api, signed, payload, worker, sessions):
    jobs, _, _ = worker
    commands = [
        '/profile {"preferred_language":"Marathi","district":"Pune",'
        '"farm_size":2,"farm_size_unit":"acre"}',
        '/crop {"crop_name":"onion","season":"rabi"}',
        '/crop {"crop_name":"tomato","variety":"local"}',
    ]
    for i, command in enumerate(commands):
        await api.post(URL, **signed(payload(f"wamid.command.{i}", command)))
        assert await jobs.tick()
    async with sessions() as session:
        profile = (await session.scalars(select(FarmerProfile))).one()
        assert profile.district == "Pune"
        crops = list(await session.scalars(select(FarmerCrop)))
        assert {crop.crop_name for crop in crops} == {"onion", "tomato"}


async def test_stale_send_is_not_blindly_replayed(api, signed, payload, worker, sessions):
    from app.repositories.message_repository import MessageRepository

    await api.post(URL, **signed(payload()))
    async with sessions() as session, session.begin():
        job = (await session.scalars(select(ProcessingJob))).one()
        inbound = await session.get(Message, job.message_id)
        reply = await MessageRepository(session).assistant(inbound, "Already generated")
        reply.send_started_at = utcnow() - timedelta(minutes=10)
        job.status = ProcessingJobStatus.PROCESSING
        job.locked_at = utcnow() - timedelta(minutes=10)
        job.locked_by = "crashed-worker"
    jobs, chatbot, whatsapp = worker
    assert await jobs.tick()
    chatbot.reply.assert_not_awaited()
    whatsapp.send_text.assert_not_awaited()
    async with sessions() as session:
        job = (await session.scalars(select(ProcessingJob))).one()
        assert job.status == ProcessingJobStatus.FAILED
        assert job.last_error == "delivery_uncertain"


async def test_future_queued_turn_is_not_in_earlier_history(api, signed, payload, worker):
    jobs, chatbot, _ = worker
    await api.post(URL, **signed(payload("wamid.a", "Onion is yellow")))
    await api.post(URL, **signed(payload("wamid.b", "45 days old")))
    assert await jobs.tick()
    first_history = chatbot.reply.call_args.args[0]
    assert len(first_history) == 1
    assert "45" not in first_history[0].text
    assert await jobs.tick()
    assert len(chatbot.reply.call_args.args[0]) == 3
