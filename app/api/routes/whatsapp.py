import hashlib
import json
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import session_dependency, settings_dependency
from app.core.config import Settings
from app.core.exceptions import WebhookAuthenticationError
from app.core.security import secure_compare
from app.integrations.whatsapp.parser import parse_webhook
from app.integrations.whatsapp.signature import valid_signature
from app.repositories.webhook_repository import WebhookRepository
from app.services.message_service import MessageService
from app.utils.datetime import utcnow

router = APIRouter(prefix="/api/v1/webhooks")
logger = logging.getLogger(__name__)


@router.get("/whatsapp", response_class=PlainTextResponse)
async def verify(
    request: Request, settings: Annotated[Settings, Depends(settings_dependency)]
) -> str:
    query = request.query_params
    if query.get("hub.mode") != "subscribe" or not secure_compare(
        query.get("hub.verify_token", ""), settings.meta_verify_token.get_secret_value()
    ):
        raise HTTPException(403, "Webhook verification failed")
    challenge = query.get("hub.challenge")
    if not challenge:
        raise HTTPException(400, "Missing challenge")
    return challenge


@router.post("/whatsapp")
async def webhook(
    request: Request,
    settings: Annotated[Settings, Depends(settings_dependency)],
    session: Annotated[AsyncSession, Depends(session_dependency)],
) -> dict[str, str]:
    logger.info("webhook_received")
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > settings.webhook_max_bytes:
            raise HTTPException(413, "Request too large")
    raw = bytes(body)
    if not valid_signature(
        raw,
        request.headers.get("x-hub-signature-256", ""),
        settings.meta_app_secret.get_secret_value(),
    ):
        logger.warning("signature_invalid")
        raise WebhookAuthenticationError()
    logger.info("signature_valid")
    parsed = parse_webhook(
        raw, settings.meta_phone_number_id, settings.meta_whatsapp_business_account_id
    )
    async with session.begin():
        event = await WebhookRepository(session).add(
            "envelope:" + hashlib.sha256(raw).hexdigest(), "envelope", json.loads(raw)
        )
        if event is None:
            logger.info("duplicate_detected")
        else:
            await MessageService(session).ingest(parsed, settings.job_max_attempts)
            event.processed = True
            event.processed_at = utcnow()
            logger.info("webhook_persisted", extra={"event_id": event.id})
    return {"status": "accepted"}
