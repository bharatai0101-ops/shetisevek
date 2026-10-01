from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DealInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=200)
    partner: str = Field(min_length=1, max_length=200)
    company_name: str = Field(min_length=1, max_length=200)
    contact_person: str = Field(default="", max_length=128)
    phone: str = Field(default="", max_length=32)
    email: str = Field(default="", max_length=200)
    gst_number: str = Field(default="", max_length=32)
    address: str = Field(default="", max_length=4000)
    region: str = Field(min_length=1, max_length=128)
    start: date
    end: date
    terms: str = Field(default="", max_length=4000)
    status: Literal["Active", "Paused", "Draft"] = "Active"

    @model_validator(mode="after")
    def valid_dates(self) -> "DealInput":
        if self.end < self.start:
            raise ValueError("End date must be on or after start date")
        return self


class FinanceLogin(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=1, max_length=200)
