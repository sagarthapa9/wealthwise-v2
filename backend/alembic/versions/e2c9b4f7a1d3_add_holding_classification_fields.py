"""add holding classification, financial metadata, and currency columns

Revision ID: e2c9b4f7a1d3
Revises: 5d39d57103a8
Create Date: 2026-06-05 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e2c9b4f7a1d3"
down_revision: Union[str, Sequence[str], None] = "5d39d57103a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Classification fields (populated from ticker provider at creation)
    op.add_column("holdings", sa.Column("type", sa.String(20), nullable=True))
    op.add_column("holdings", sa.Column("asset_class", sa.String(30), nullable=True))
    op.add_column("holdings", sa.Column("sector", sa.String(40), nullable=True))
    op.add_column("holdings", sa.Column("geography", sa.String(30), nullable=True))
    op.add_column("holdings", sa.Column("currency", sa.String(3), nullable=True))

    # Financial metadata (from ticker provider)
    op.add_column("holdings", sa.Column("ocf_pct", sa.Float(), nullable=True))
    op.add_column("holdings", sa.Column("dividend_yield_pct", sa.Float(), nullable=True))
    op.add_column("holdings", sa.Column("isin", sa.String(12), nullable=True))


def downgrade() -> None:
    op.drop_column("holdings", "isin")
    op.drop_column("holdings", "dividend_yield_pct")
    op.drop_column("holdings", "ocf_pct")
    op.drop_column("holdings", "currency")
    op.drop_column("holdings", "geography")
    op.drop_column("holdings", "sector")
    op.drop_column("holdings", "asset_class")
    op.drop_column("holdings", "type")
