"""Provision a fresh, isolated demo session: an ephemeral user pre-loaded with
seeded uploads (parsed through the real pipeline), a completed analysis,
knowledge-base docs and a welcome conversation."""

import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.base import utcnow
from app.models.analysis import Analysis
from app.models.chat import Conversation, Message
from app.models.knowledge import Document
from app.models.upload import LogEvent, Upload
from app.models.user import User
from app.services.demo import fixtures
from app.services.parsers.service import parse_file

logger = logging.getLogger(__name__)

DEMO_EMAIL_DOMAIN = "demo.opspilot.local"


def is_demo_user(user: User) -> bool:
    return user.email.endswith(f"@{DEMO_EMAIL_DOMAIN}")


async def _seed_upload(db: AsyncSession, user_id: uuid.UUID, spec: fixtures.DemoFile) -> Upload:
    """Write the fixture to disk and parse it through the real parser pipeline."""
    settings = get_settings()
    upload_id = uuid.uuid4()
    ext = Path(spec.filename).suffix or ".log"
    dest_dir = Path(settings.upload_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{upload_id}{ext}"
    dest.write_text(spec.content, encoding="utf-8")

    upload = Upload(
        id=upload_id,
        user_id=user_id,
        filename=spec.filename,
        content_type="text/plain",
        size_bytes=len(spec.content.encode("utf-8")),
        storage_path=str(dest),
        status="parsing",
    )
    db.add(upload)
    await db.flush()

    result = parse_file(dest, spec.filename)
    for event in result.events:
        db.add(
            LogEvent(
                upload_id=upload.id,
                timestamp=event.timestamp,
                source=event.source,
                host=event.host[:255],
                severity=event.severity,
                event_id=event.event_id[:60],
                message=event.message,
                raw=event.raw,
            )
        )
    upload.source_type = result.source_type
    upload.record_count = len(result.events)
    upload.status = "parsed"
    await db.flush()
    return upload


async def create_demo_session(db: AsyncSession) -> User:
    """Create a fully populated, isolated demo user. Commits and returns the user."""
    token = uuid.uuid4().hex[:12]
    user = User(
        email=f"demo-{token}@{DEMO_EMAIL_DOMAIN}",
        hashed_password=hash_password(uuid.uuid4().hex),  # unguessable; login is via issued JWT
        full_name="Demo User",
        is_admin=False,
    )
    db.add(user)
    await db.flush()

    # Uploads (parsed for real) + one pre-baked completed analysis
    for spec in fixtures.demo_files():
        upload = await _seed_upload(db, user.id, spec)
        if spec.analysis:
            a = spec.analysis
            db.add(
                Analysis(
                    user_id=user.id,
                    upload_id=upload.id,
                    status="completed",
                    model="demo-seed",
                    summary=a["summary"],
                    root_cause=a["root_cause"],
                    severity=a["severity"],
                    confidence=a["confidence"],
                    affected_systems=a["affected_systems"],
                    remediation=a["remediation"],
                    scripts=a["scripts"],
                    evidence=a["evidence"],
                    completed_at=utcnow(),
                )
            )

    # Welcome conversation
    convo_spec = fixtures.demo_conversation()
    conversation = Conversation(user_id=user.id, title=convo_spec.title)
    db.add(conversation)
    await db.flush()
    for role, content in convo_spec.messages:
        db.add(Message(conversation_id=conversation.id, role=role, content=content, meta={}))

    # Knowledge base. Embedding is network I/O, so never run it inside this request
    # session: enqueue it (a worker embeds it for full RAG). If no broker is reachable,
    # store a plain, immediately-visible Document so the demo is still populated.
    from app.workers.tasks import ingest_document_task  # lazy: avoids task↔seed import cycle

    for doc in fixtures.demo_docs():
        try:
            ingest_document_task.delay(str(user.id), doc.title, doc.text, doc.doc_type, "demo")
        except Exception:
            logger.warning("Demo doc queue unavailable; storing without vectors", exc_info=True)
            db.add(
                Document(
                    user_id=user.id, title=doc.title, doc_type=doc.doc_type,
                    source="demo", status="ready",
                )
            )

    await db.commit()
    await db.refresh(user)
    logger.info("Created demo session for %s", user.email)
    return user


async def purge_expired_demo_users(db: AsyncSession, ttl_minutes: int) -> int:
    """Delete demo users (and, via cascade, all their data + files) older than the TTL.

    Returns the number of sessions purged."""
    from sqlalchemy import select

    cutoff = datetime.now(UTC).timestamp() - ttl_minutes * 60
    rows = list(
        (
            await db.execute(
                select(User).where(User.email.like(f"demo-%@{DEMO_EMAIL_DOMAIN}"))
            )
        ).scalars()
    )
    purged = 0
    for user in rows:
        created = user.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
        if created.timestamp() >= cutoff:
            continue
        # Remove upload files before the DB cascade drops their rows
        uploads = list(
            (await db.execute(select(Upload).where(Upload.user_id == user.id))).scalars()
        )
        for upload in uploads:
            Path(upload.storage_path).unlink(missing_ok=True)
        await db.delete(user)
        purged += 1
    if purged:
        await db.commit()
        logger.info("Purged %d expired demo session(s)", purged)
    return purged
