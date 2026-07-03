import redis.asyncio as aioredis
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(db: AsyncSession = Depends(get_db)) -> dict:
    settings = get_settings()
    status: dict = {"api": "ok", "llm_provider": settings.llm_provider}
    try:
        await db.execute(text("SELECT 1"))
        status["database"] = "ok"
    except Exception as exc:
        status["database"] = f"error: {type(exc).__name__}"
    try:
        client = aioredis.from_url(settings.redis_url)
        await client.ping()
        await client.aclose()
        status["redis"] = "ok"
    except Exception as exc:
        status["redis"] = f"error: {type(exc).__name__}"
    status["status"] = (
        "ok" if status["database"] == "ok" and status["redis"] == "ok" else "degraded"
    )
    return status
