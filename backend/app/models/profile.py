"""Profile ORM model — stores investor personal context."""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    age: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    risk_tolerance: Mapped[str] = mapped_column(String(20), nullable=False, default="moderate")
    investment_horizon: Mapped[str] = mapped_column(String(100), nullable=False, default="5+ years")
    primary_goal: Mapped[str] = mapped_column(String(200), nullable=False, default="wealth accumulation")
    income_band: Mapped[str] = mapped_column(String(50), nullable=False, default="£50k-£100k")
    tax_band: Mapped[str] = mapped_column(String(30), nullable=False, default="basic_rate")
    pension_contributions_monthly: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    isa_contributions_monthly: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
