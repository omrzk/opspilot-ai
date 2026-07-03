"""Database access for Celery tasks.

Each task run creates a fresh engine with NullPool: Celery tasks call
asyncio.run(), so pooled asyncpg connections must never outlive the event
loop that created them."""

from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings


@asynccontextmanager
async def task_session():
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            yield session
    finally:
        await engine.dispose()
