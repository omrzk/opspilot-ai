"""Demo endpoints: one-click ephemeral, sandboxed session.

Only mounted when OPSPILOT_DEMO_MODE is enabled. Each call to /demo/start creates
a brand-new isolated user seeded with a realistic environment and returns a short-
lived JWT. Sessions auto-expire and are purged by a periodic worker task."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.security import create_access_token
from app.db.session import get_db
from app.models.analysis import Analysis
from app.models.chat import Message
from app.models.user import User
from app.schemas.auth import TokenOut, UserOut
from app.services.demo.seed import create_demo_session, is_demo_user

router = APIRouter(prefix="/demo", tags=["demo"])


def _require_demo_enabled() -> None:
    if not get_settings().demo_mode:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Demo mode is not enabled")


@router.get("/status")
async def demo_status() -> dict:
    settings = get_settings()
    return {
        "demo_mode": settings.demo_mode,
        "session_ttl_minutes": settings.demo_session_ttl_minutes,
        "limits": {
            "max_analyses": settings.demo_max_analyses,
            "max_chat_messages": settings.demo_max_chat_messages,
            "max_upload_mb": settings.demo_max_upload_mb,
        },
    }


@router.post("/start", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
async def start_demo(db: AsyncSession = Depends(get_db)) -> TokenOut:
    _require_demo_enabled()
    settings = get_settings()
    user = await create_demo_session(db)
    token = create_access_token(str(user.id), expires_minutes=settings.demo_session_ttl_minutes)
    return TokenOut(access_token=token, user=UserOut.model_validate(user))


async def enforce_demo_analysis_quota(db: AsyncSession, user: User) -> None:
    """Raise 429 if a demo user has hit their analysis cap. No-op for real users."""
    settings = get_settings()
    if not settings.demo_mode or not is_demo_user(user):
        return
    used = await db.scalar(select(func.count(Analysis.id)).where(Analysis.user_id == user.id))
    # The seeded analysis doesn't count against the visitor's budget.
    seeded = await db.scalar(
        select(func.count(Analysis.id)).where(
            Analysis.user_id == user.id, Analysis.model == "demo-seed"
        )
    )
    if (used or 0) - (seeded or 0) >= settings.demo_max_analyses:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Demo limit reached ({settings.demo_max_analyses} analyses per session). "
            "Start a new demo session to continue.",
        )


async def enforce_demo_chat_quota(db: AsyncSession, user: User) -> None:
    settings = get_settings()
    if not settings.demo_mode or not is_demo_user(user):
        return
    used = await db.scalar(
        select(func.count(Message.id))
        .join(Message.conversation)
        .where(Message.role == "user")
        .where(Message.conversation.has(user_id=user.id))
    )
    if (used or 0) >= settings.demo_max_chat_messages:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Demo chat limit reached ({settings.demo_max_chat_messages} messages per session). "
            "Start a new demo session to continue.",
        )


@router.get("/me", response_model=UserOut)
async def demo_me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(user)
