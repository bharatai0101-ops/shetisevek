from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.constants import FarmerCropStatus


class FarmerProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    preferred_language: str | None = Field(default=None, max_length=64)
    state: str | None = Field(default=None, max_length=128)
    district: str | None = Field(default=None, max_length=128)
    village: str | None = Field(default=None, max_length=128)
    farm_size: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=3)
    farm_size_unit: str | None = Field(default=None, max_length=32)
    soil_type: str | None = Field(default=None, max_length=128)
    irrigation_type: str | None = Field(default=None, max_length=128)


class CropCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    crop_name: str = Field(min_length=1, max_length=128)
    variety: str | None = Field(default=None, max_length=128)
    season: str | None = Field(default=None, max_length=64)
    sowing_date: date | None = None
    area: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=3)
    area_unit: str | None = Field(default=None, max_length=32)
    status: FarmerCropStatus = FarmerCropStatus.ACTIVE


class CropRead(CropCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID


class FarmerContext(BaseModel):
    profile: FarmerProfileUpdate
    crops: list[CropRead]
