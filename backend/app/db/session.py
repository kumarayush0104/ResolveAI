from typing import AsyncGenerator
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
)

from backend.app.config import settings
from backend.app.db.models import Base

# Async engine for application runtime
connect_args = {}
if "sqlite" in settings.async_database_url:
    connect_args["check_same_thread"] = False

async_engine = create_async_engine(
    settings.async_database_url,
    echo=False,
    connect_args=connect_args,
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


def init_db_sync() -> None:
    """Create all database tables using sync engine (useful for SQLite initialization)."""
    sync_url = settings.DATABASE_URL
    if sync_url.startswith("sqlite+aiosqlite://"):
        sync_url = sync_url.replace("sqlite+aiosqlite://", "sqlite://")
    sync_connect_args = {}
    if "sqlite" in sync_url:
        sync_connect_args["check_same_thread"] = False

    engine = create_engine(sync_url, connect_args=sync_connect_args)
    Base.metadata.create_all(bind=engine)


async def init_db() -> None:
    """Initialize database tables asynchronously."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for obtaining an async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
