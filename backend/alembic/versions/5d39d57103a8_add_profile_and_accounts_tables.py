"""add profile and accounts tables

Revision ID: 5d39d57103a8
Revises: f87dd7bb818c
Create Date: 2026-06-03 00:22:07.002605
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "5d39d57103a8"
down_revision: Union[str, Sequence[str], None] = "f87dd7bb818c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create profiles table
    op.create_table(
        "profiles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("age", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("risk_tolerance", sa.String(20), nullable=False, server_default="moderate"),
        sa.Column("investment_horizon", sa.String(100), nullable=False, server_default="5+ years"),
        sa.Column("primary_goal", sa.String(200), nullable=False, server_default="wealth accumulation"),
        sa.Column("income_band", sa.String(50), nullable=False, server_default="£50k-£100k"),
        sa.Column("tax_band", sa.String(30), nullable=False, server_default="basic_rate"),
        sa.Column("pension_contributions_monthly", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("isa_contributions_monthly", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create accounts table
    op.create_table(
        "accounts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("provider", sa.String(100), nullable=False, server_default="Manual Entry"),
        sa.Column("account_type", sa.String(10), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="GBP"),
        sa.Column("cash_balance", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # Add account_id FK to holdings table
    op.add_column(
        "holdings",
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("holdings", "account_id")
    op.drop_table("accounts")
    op.drop_table("profiles")
