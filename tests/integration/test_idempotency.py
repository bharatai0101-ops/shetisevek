import asyncio
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import func, select

from app.models import Conversation, FarmerProfile, Message, ProcessingJob, User
from app.workers.job_service import JobService

pytestmark = pytest.mark.integration
URL = "/api/v1/webhooks/whatsapp"


async def test_atomic_creation_and_duplicate_webhooks(api, sessions, signed, payload, worker):
    data = payload()
    results = await asyncio.gather(*(api.post(URL, **signed(data)) for _ in range(4)))
    assert all(result.status_code == 200 for result in results)
    # Same message ID in a differently encoded/enveloped delivery remains idempotent.
    data["ignored"] = "another envelope"
    assert (await api.post(URL, **signed(data))).status_code == 200
    async with sessions() as session:
        for model in (User, FarmerProfile, Conversation, Message, ProcessingJob):
            assert await session.scalar(select(func.count()).select_from(model)) == 1
    jobs, chatbot, whatsapp = worker
    assert await jobs.tick()
    assert not await jobs.tick()
    chatbot.reply.assert_awaited_once()
    whatsapp.send_text.assert_awaited_once()


async def test_concurrent_workers_do_not_generate_same_job(api, signed, payload, worker, engine):
    await api.post(URL, **signed(payload()))
    jobs, chatbot, _ = worker
    started = asyncio.Event()
    release = asyncio.Event()

    async def generate(*args):
        started.set()
        await release.wait()
        return "Reply"

    chatbot.reply = AsyncMock(side_effect=generate)
    another = JobService(engine, jobs.processor, "second-worker")
    task = asyncio.create_task(jobs.tick())
    await asyncio.wait_for(started.wait(), 10)
    try:
        assert not await another.tick()
    finally:
        release.set()
        await task
    chatbot.reply.assert_awaited_once()


async def test_overlapping_batches_are_atomic(api, signed, payload, sessions):
    batch = payload("wamid.a")
    batch["entry"][0]["changes"][0]["value"]["messages"].extend(
        payload("wamid.b")["entry"][0]["changes"][0]["value"]["messages"]
    )
    responses = await asyncio.gather(
        api.post(URL, **signed(batch)), api.post(URL, **signed(payload("wamid.b")))
    )
    assert all(response.status_code == 200 for response in responses)
    async with sessions() as session:
        assert await session.scalar(select(func.count()).select_from(Message)) == 2
        assert await session.scalar(select(func.count()).select_from(ProcessingJob)) == 2


async def test_two_users_can_be_processed_independently(api, signed, payload, worker, engine):
    jobs, chatbot, _ = worker
    await api.post(URL, **signed(payload("wamid.a")))
    await api.post(URL, **signed(payload("wamid.b", sender="919000000002")))
    second = JobService(engine, jobs.processor, "worker-two")
    results = await asyncio.gather(jobs.tick(), second.tick())
    # A claim may briefly skip the other worker's locked candidate batch. Next poll picks it up.
    if chatbot.reply.await_count < 2:
        await second.tick()
    assert any(results)
    assert chatbot.reply.await_count == 2


async def test_lost_claim_does_not_send_or_overwrite_new_owner(
    api, signed, payload, worker, sessions
):
    from sqlalchemy import update

    jobs, chatbot, whatsapp = worker
    await api.post(URL, **signed(payload()))

    async def generation_after_ownership_change(*args):
        # Simulate a fenced-out worker resuming after another owner reclaimed its job.
        async with sessions() as session, session.begin():
            await session.execute(update(ProcessingJob).values(locked_by="replacement-worker"))
        return "Stale answer"

    chatbot.reply.side_effect = generation_after_ownership_change
    assert await jobs.tick()
    whatsapp.send_text.assert_not_awaited()
    async with sessions() as session:
        job = (await session.scalars(select(ProcessingJob))).one()
        assert job.locked_by == "replacement-worker"
        assert await session.scalar(select(func.count()).select_from(Message)) == 1
