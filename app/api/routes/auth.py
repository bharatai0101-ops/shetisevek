"""Validate administrator credentials for the trusted frontend server."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, SecretStr

from app.api.dependencies import settings_dependency
from app.api.routes.commerce import require_admin
from app.core.config import Settings
from app.core.security import secure_compare

router = APIRouter(prefix="/api/v1/admin/auth", dependencies=[Depends(require_admin)])


class AdminLogin(BaseModel):
    email: str = Field(min_length=3, max_length=200)
    password: SecretStr = Field(min_length=1, max_length=200)


@router.post("/login")
async def login(
    data: AdminLogin, settings: Annotated[Settings, Depends(settings_dependency)]
) -> dict[str, str]:
    email = settings.admin_email.strip().lower()
    password = settings.admin_password.get_secret_value()
    if not email or not password:
        raise HTTPException(503, "Admin login is not configured")
    email_ok = secure_compare(data.email.strip().lower(), email)
    password_ok = secure_compare(data.password.get_secret_value(), password)
    if not (email_ok and password_ok):
        raise HTTPException(401, "Incorrect email or password")
    return {"email": email}
