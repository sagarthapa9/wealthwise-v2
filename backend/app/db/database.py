"""
Database engine, session factory, and FastAPI dependency.

- ``engine`` manages the connection pool to PostgreSQL
- ``AsyncSessionLocal`` creates one session per request
- ``get_db`` is a FastAPI dependency — injects a session, closes it when done
- ``Base`` is the declarative base all ORM models inherit from
"""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

# Async engine — connects to PostgreSQL via asyncpg driver
# pool_size=5 means up to 5 connections are kept open and reused
engine = create_async_engine(
    settings.database_url,
    echo=False,          # Set True to see SQL queries in logs
    pool_size=5,
)

# Session factory — call this to get a fresh DB session
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Keep objects usable after commit
)


# Declarative base — all models inherit from this
class Base(DeclarativeBase):
    pass


async def get_db():
    """FastAPI dependency. Yields an AsyncSession and closes it after the request.

    Usage in a route:
        @router.get("/holdings")
        async def list_holdings(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
