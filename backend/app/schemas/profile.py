"""Pydantic schemas for user profile / PersonalContext."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ProfileUpdate(BaseModel):
    age: int = Field(..., ge=18, le=120, examples=[35])
    risk_tolerance: Literal["low", "moderate", "high"] = "moderate"
    investment_horizon: str = Field(..., min_length=1, max_length=100)
    primary_goal: str = Field(..., min_length=1, max_length=200)
    income_band: str = Field(..., max_length=50)
    tax_band: Literal["basic_rate", "higher_rate", "additional_rate"] = "basic_rate"
    pension_contributions_monthly: int = Field(default=0, ge=0)
    isa_contributions_monthly: int = Field(default=0, ge=0)


class ProfileResponse(BaseModel):
    id: int
    age: int
    risk_tolerance: str
    investment_horizon: str
    primary_goal: str
    income_band: str
    tax_band: str
    pension_contributions_monthly: int
    isa_contributions_monthly: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
