"""Account ORM model — one row = one brokerage account (ISA, SIPP, GIA, LISA)."""

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(100), nullable=False, default="Manual Entry")
    account_type: Mapped[str] = mapped_column(String(10), nullable=False)  # SIPP, ISA, GIA, LISA
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="GBP")
    cash_balance: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
