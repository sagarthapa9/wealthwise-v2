"""align chat_sessions.session_id to a single unique index

The model declares session_id as ``unique=True, index=True``, which SQLAlchemy
renders as ONE unique index. The original create_chat_tables migration instead
created a separate unique constraint PLUS a non-unique index — redundant, and a
drift source that fails ``alembic check``. This replaces both with a single
unique index so the schema matches the model.

Revision ID: c7d8e9f0a1b2
Revises: b5c6d7e8f9a0
Create Date: 2026-08-16 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op

revision: str = "c7d8e9f0a1b2"
down_revision: Union[str, Sequence[str], None] = "b5c6d7e8f9a0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Replace (unique constraint + non-unique index) with a single unique index.
    op.drop_constraint("chat_sessions_session_id_key", "chat_sessions", type_="unique")
    op.drop_index("ix_chat_sessions_session_id", table_name="chat_sessions")
    op.create_index(
        "ix_chat_sessions_session_id",
        "chat_sessions",
        ["session_id"],
        unique=True,
    )


def downgrade() -> None:
    # Restore the original redundant pair.
    op.drop_index("ix_chat_sessions_session_id", table_name="chat_sessions")
    op.create_index(
        "ix_chat_sessions_session_id",
        "chat_sessions",
        ["session_id"],
        unique=False,
    )
    op.create_unique_constraint(None, "chat_sessions", ["session_id"])
