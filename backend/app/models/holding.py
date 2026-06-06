"""Holding ORM model — one row = one investment position in the portfolio."""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class Holding(Base):
    __tablename__ = "holdings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(10), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    cost_basis_per_share: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    current_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    account_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True
    )

    # ── Classification fields (populated from ticker provider at creation) ──
    type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    asset_class: Mapped[str | None] = mapped_column(String(30), nullable=True)
    sector: Mapped[str | None] = mapped_column(String(40), nullable=True)
    geography: Mapped[str | None] = mapped_column(String(30), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)

    # ── Financial metadata (from ticker provider) ──────────────────────────
    ocf_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    dividend_yield_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    isin: Mapped[str | None] = mapped_column(String(12), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
