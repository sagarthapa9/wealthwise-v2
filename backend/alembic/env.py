"""
Alembic migration environment — configures how alembic connects to the database
and which models it tracks.
"""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

from app.core.config import settings

# Import our model metadata so alembic can autogenerate migrations
from app.db.database import Base
from app.models import Holding  # noqa: F401 — registers model with Base
from app.models import ChatSession, ChatMessage, UserMemory  # noqa: F401

# Alembic Config — reads alembic.ini
config = context.config

# Use the app's real connection string (DATABASE_URL env / .env) instead of
# the value hardcoded in alembic.ini. That hardcoded URL goes stale when the
# DB password rotates — it caused "password authentication failed for user
# wealthwise" on `alembic upgrade head` while the app itself kept working.
config.set_main_option("sqlalchemy.url", settings.database_url)

# Set up Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Tell alembic about our models so it can detect changes
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode — generates SQL without a DB connection."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations inside a transaction."""
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode — connects to the DB and runs them."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Wrapper — alembic can't call async directly, so we use asyncio.run()."""
    asyncio.run(run_async_migrations())


# Entry point
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
