from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class InboundPayload(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    id: str = Field(min_length=1, max_length=512)
    sender: str = Field(alias="from", pattern=r"^\d{5,32}$")
    timestamp: str = Field(pattern=r"^\d{1,10}$")
    type: str = Field(min_length=1, max_length=64)


class StatusPayload(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str = Field(min_length=1, max_length=512)
    status: str = Field(min_length=1, max_length=32)
    timestamp: str = Field(pattern=r"^\d{1,10}$")
    biz_opaque_callback_data: str | None = None
    errors: list[dict[str, Any]] = Field(default_factory=list)


class WebhookValue(BaseModel):
    model_config = ConfigDict(extra="allow")
    metadata: dict[str, Any] = Field(default_factory=dict)
    contacts: list[dict[str, Any]] = Field(default_factory=list)
    messages: list[InboundPayload] = Field(default_factory=list)
    statuses: list[StatusPayload] = Field(default_factory=list)


class WebhookChange(BaseModel):
    field: str
    value: WebhookValue


class WebhookEntry(BaseModel):
    id: str
    changes: list[WebhookChange] = Field(default_factory=list)


class WebhookEnvelope(BaseModel):
    object: Literal["whatsapp_business_account"]
    entry: list[WebhookEntry]
