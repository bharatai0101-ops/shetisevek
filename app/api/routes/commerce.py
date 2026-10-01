import hashlib
import hmac
import secrets
import time
from datetime import date, datetime, timedelta, timezone
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import session_dependency, settings_dependency
from app.core.config import Settings
from app.core.security import secure_compare
from app.models.commerce import Deal
from app.schemas.commerce import DealInput, FinanceLogin
from app.services.commerce_service import deal_listing, finance_report


def require_admin(
    settings: Annotated[Settings, Depends(settings_dependency)],
    token: Annotated[str, Header(alias="X-Admin-Token")] = "",
) -> None:
    expected = settings.admin_api_token.get_secret_value()
    if not expected or not secure_compare(token, expected):
        raise HTTPException(401, "Admin authentication required")


router = APIRouter(prefix="/api/v1/admin", dependencies=[Depends(require_admin)])
Session = Annotated[AsyncSession, Depends(session_dependency)]


def today_india() -> date:
    return datetime.now(timezone(timedelta(hours=5, minutes=30))).date()


@router.get("/deals")
async def list_deals(session: Session) -> dict[str, Any]:
    return await deal_listing(session, today_india())


@router.post("/deals", status_code=201)
async def create_deal(data: DealInput, session: Session) -> dict[str, UUID]:
    async with session.begin():
        deal = Deal(**data.model_dump())
        session.add(deal)
        await session.flush()
    return {"id": deal.id}


@router.put("/deals/{deal_id}")
async def update_deal(deal_id: UUID, data: DealInput, session: Session) -> dict[str, UUID]:
    async with session.begin():
        deal = await session.get(Deal, deal_id, with_for_update=True)
        if deal is None:
            raise HTTPException(404, "Deal not found")
        for key, value in data.model_dump().items():
            setattr(deal, key, value)
    return {"id": deal.id}


@router.delete("/deals/{deal_id}", status_code=204)
async def delete_deal(deal_id: UUID, session: Session) -> Response:
    async with session.begin():
        deal = await session.get(Deal, deal_id, with_for_update=True)
        if deal is None:
            raise HTTPException(404, "Deal not found")
        await session.delete(deal)
    return Response(status_code=204)


@router.post("/finance/login")
async def finance_login(
    data: FinanceLogin, settings: Annotated[Settings, Depends(settings_dependency)]
) -> dict[str, Any]:
    email = settings.finance_email.strip().lower()
    password = settings.finance_password.get_secret_value()
    if not email or not password:
        raise HTTPException(503, "Finance login is not configured")
    email_ok = secure_compare(data.email.strip().lower(), email)
    password_ok = secure_compare(data.password, password)
    if not (email_ok and password_ok):
        raise HTTPException(401, "Incorrect email or password")
    payload = f"{int(time.time())}:{secrets.token_hex(16)}"
    signature = hmac.new(
        settings.finance_password.get_secret_value().encode(), payload.encode(), hashlib.sha256
    ).hexdigest()
    return {"ok": True, "token": payload + ":" + signature}


def require_finance(
    settings: Annotated[Settings, Depends(settings_dependency)],
    token: Annotated[str, Header(alias="X-Finance-Token")] = "",
) -> None:
    try:
        timestamp, nonce, signature = token.split(":")
        age = time.time() - int(timestamp)
        payload = timestamp + ":" + nonce
        expected = hmac.new(
            settings.finance_password.get_secret_value().encode(), payload.encode(), hashlib.sha256
        ).hexdigest()
        valid = (
            bool(settings.finance_password.get_secret_value())
            and 0 <= age < 8 * 3600
            and secure_compare(signature, expected)
        )
    except (ValueError, TypeError):
        valid = False
    if not valid:
        raise HTTPException(401, "Finance login required")


@router.get("/finance/report", dependencies=[Depends(require_finance)])
async def report(session: Session) -> dict[str, Any]:
    return await finance_report(session, today_india())
