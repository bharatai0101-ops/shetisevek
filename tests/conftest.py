import hashlib
import hmac
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest
from sqlalchemy import text

from app.core.config import Settings
from app.db.session import make_engine, make_sessions
from app.main import create_app
from app.workers.job_service import JobService
from app.workers.processor import Processor


@pytest.fixture
def settings():
    return Settings(
        _env_file=None,
        app_env="test",
        database_url=os.getenv(
            "TEST_DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test"
        ),
        meta_verify_token="verify-test-secret",
        meta_app_secret="app-test-secret",
        meta_access_token="test-access-token",
        meta_phone_number_id="111",
        meta_whatsapp_business_account_id="222",
        meta_graph_api_version="v23.0",
        gemini_api_key="test-gemini-key",
        gemini_model="test-model",
    )


@pytest.fixture(scope="session")
def migrated_database():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to a dedicated PostgreSQL database ending in _test")
    if not url.split("?")[0].endswith("_test"):
        pytest.fail("Refusing to truncate a database whose name does not end in _test")
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        env={**os.environ, "DATABASE_URL": url},
        check=True,
        capture_output=True,
    )


@pytest.fixture
async def engine(settings, migrated_database):
    database = make_engine(settings)
    async with database.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE processing_jobs, messages, conversations, farmer_crops, "
                "farmer_profiles, users, webhook_events RESTART IDENTITY CASCADE"
            )
        )
    yield database
    await database.dispose()


@pytest.fixture
def sessions(engine):
    return make_sessions(engine)


@pytest.fixture
async def api(settings, engine):
    app = create_app(settings, engine)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client


@pytest.fixture
def payload():
    def factory(
        message_id="wamid.in.1", body="माझ्या कांद्याची पाने पिवळी पडत आहेत", sender="919000000001"
    ):
        data = json.loads(
            Path("tests/fixtures/whatsapp_text_message.json").read_text(encoding="utf-8")
        )
        value = data["entry"][0]["changes"][0]["value"]
        value["messages"][0].update(
            {"id": message_id, "from": sender, "timestamp": str(int(time.time()))}
        )
        value["messages"][0]["text"]["body"] = body
        value["contacts"][0]["wa_id"] = sender
        return data

    return factory


@pytest.fixture
def signed():
    def sign(payload):
        body = json.dumps(payload, ensure_ascii=False).encode()
        signature = "sha256=" + hmac.new(b"app-test-secret", body, hashlib.sha256).hexdigest()
        return {"content": body, "headers": {"x-hub-signature-256": signature}}

    return sign


@pytest.fixture
def worker(settings, engine):
    chatbot = AsyncMock()
    chatbot.reply.return_value = "कांद्याची जुनी पाने पिवळी आहेत की नवीन? पीक किती दिवसांचे आहे?"
    whatsapp = AsyncMock()

    async def send(recipient, text, message_id):
        mid = f"wamid.out.{message_id}"
        return mid, {"messages": [{"id": mid}]}

    whatsapp.send_text.side_effect = send
    processor = Processor(settings, chatbot, whatsapp)
    return JobService(engine, processor, "test-worker"), chatbot, whatsapp
