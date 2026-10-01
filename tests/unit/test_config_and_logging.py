import json
import logging

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.core.logging import JsonFormatter
from app.integrations.gemini.client import create_gemini_client


def test_blank_credentials_fail(settings):
    values = settings.model_dump()
    values["meta_app_secret"] = ""
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **values)


def test_production_debug_rejected(settings):
    values = settings.model_dump()
    values.update(app_env="production", debug=True)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **values)


def test_logs_drop_unapproved_fields_and_library_text():
    record = logging.LogRecord("httpx", logging.ERROR, __file__, 1, "secret token", (), None)
    record.phone_number = "919000000001"
    result = JsonFormatter().format(record)
    assert "secret token" not in result
    assert "919000000001" not in result
    assert json.loads(result)["event"] == "library_event"


async def test_real_sdk_client_constructs_and_closes_without_requests(settings):
    client = create_gemini_client(settings)
    await client.aio.aclose()
    client.close()
