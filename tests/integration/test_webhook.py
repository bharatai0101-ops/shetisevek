from unittest.mock import AsyncMock

import httpx
import pytest

from app.api.dependencies import session_dependency
from app.main import create_app

pytestmark = pytest.mark.integration
URL = "/api/v1/webhooks/whatsapp"


async def test_verification_success(api):
    response = await api.get(
        URL,
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "verify-test-secret",
            "hub.challenge": "123456",
        },
    )
    assert response.status_code == 200
    assert response.text == "123456"
    assert response.headers["x-content-type-options"] == "nosniff"


async def test_invalid_token(api):
    assert (
        await api.get(URL, params={"hub.mode": "subscribe", "hub.verify_token": "bad"})
    ).status_code == 403


async def test_invalid_signature(api, payload):
    assert (await api.post(URL, json=payload())).status_code == 401


async def test_malformed_authenticated_payload(api, signed):
    assert (await api.post(URL, **signed({"bad": "payload"}))).status_code == 400


async def test_health_and_ready(api):
    assert (await api.get("/health")).status_code == 200
    assert (await api.get("/ready")).status_code == 200


async def test_readiness_failure_is_safe(settings):
    app = create_app(settings)

    async def broken_session():
        session = AsyncMock()
        session.execute.side_effect = RuntimeError("secret database password")
        yield session

    app.dependency_overrides[session_dependency] = broken_session
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as c:
        response = await c.get("/ready")
    assert response.status_code == 503
    assert "secret" not in response.text


async def test_oversized_request(api):
    assert (await api.post(URL, content=b"x" * (1048576 + 1))).status_code == 413


async def test_database_error_never_acknowledges(settings, signed, payload):
    from sqlalchemy.exc import OperationalError

    app = create_app(settings)

    class BrokenSession:
        def begin(self):
            raise OperationalError("secret SQL", {}, Exception("secret database password"))

    async def broken_session():
        yield BrokenSession()

    app.dependency_overrides[session_dependency] = broken_session
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as c:
            response = await c.post(URL, **signed(payload()))
    assert response.status_code == 503
    assert "secret" not in response.text
