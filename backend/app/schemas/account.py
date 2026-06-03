"""Pydantic schemas for accounts."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class AccountCreate(BaseModel):
    provider: str = Field(..., min_length=1, max_length=100)
    account_type: Literal["SIPP", "ISA", "GIA", "LISA"]
    currency: Literal["GBP", "USD", "EUR"] = "GBP"
    cash_balance: float = Field(default=0.0, ge=0)


class AccountUpdate(BaseModel):
    provider: str | None = None
    account_type: Literal["SIPP", "ISA", "GIA", "LISA"] | None = None
    currency: Literal["GBP", "USD", "EUR"] | None = None
    cash_balance: float | None = Field(default=None, ge=0)


class AccountResponse(BaseModel):
    id: int
    provider: str
    account_type: str
    currency: str
    cash_balance: float
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
