"""File uploads: store, enqueue parsing, browse parsed events."""

import uuid
from pathlib import Path

import anyio
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.db.session import get_db
from app.models.upload import LogEvent, Upload
from app.models.user import User
from app.schemas.upload import LogEventOut, UploadOut
from app.workers.tasks import parse_upload_task

router = APIRouter(prefix="/uploads", tags=["uploads"])

ALLOWED_EXTENSIONS = {".evtx", ".json", ".ndjson", ".jsonl", ".txt", ".log", ".csv", ".tsv", ".xml"}
CHUNK_SIZE = 1024 * 1024


@router.post("", response_model=UploadOut, status_code=status.HTTP_201_CREATED)
async def create_upload(
    file: UploadFile,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UploadOut:
    settings = get_settings()
    filename = Path(file.filename or "upload").name
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    upload_id = uuid.uuid4()
    dest_dir = Path(settings.upload_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{upload_id}{ext}"

    max_mb = settings.demo_max_upload_mb if settings.demo_mode else settings.max_upload_mb
    max_bytes = max_mb * 1024 * 1024
    size = 0
    async with await anyio.open_file(dest, "wb") as out:
        while chunk := await file.read(CHUNK_SIZE):
            size += len(chunk)
            if size > max_bytes:
                await out.aclose()
                dest.unlink(missing_ok=True)
                raise HTTPException(
                    status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    f"File exceeds {max_mb} MB limit",
                )
            await out.write(chunk)
    if size == 0:
        dest.unlink(missing_ok=True)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Empty file")

    upload = Upload(
        id=upload_id,
        user_id=user.id,
        filename=filename,
        content_type=file.content_type or "",
        size_bytes=size,
        storage_path=str(dest),
        status="pending",
    )
    db.add(upload)
    await db.commit()
    await db.refresh(upload)

    parse_upload_task.delay(str(upload.id))
    return UploadOut.model_validate(upload)


@router.get("", response_model=list[UploadOut])
async def list_uploads(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[UploadOut]:
    rows = (
        await db.execute(
            select(Upload).where(Upload.user_id == user.id).order_by(Upload.created_at.desc())
        )
    ).scalars()
    return [UploadOut.model_validate(u) for u in rows]


async def _owned_upload(db: AsyncSession, user: User, upload_id: uuid.UUID) -> Upload:
    upload = await db.get(Upload, upload_id)
    if upload is None or upload.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Upload not found")
    return upload


@router.get("/{upload_id}", response_model=UploadOut)
async def get_upload(
    upload_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UploadOut:
    return UploadOut.model_validate(await _owned_upload(db, user, upload_id))


@router.get("/{upload_id}/events")
async def list_events(
    upload_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    severity: str | None = None,
) -> dict:
    upload = await _owned_upload(db, user, upload_id)
    query = select(LogEvent).where(LogEvent.upload_id == upload.id)
    count_query = select(func.count(LogEvent.id)).where(LogEvent.upload_id == upload.id)
    if severity:
        query = query.where(LogEvent.severity == severity)
        count_query = count_query.where(LogEvent.severity == severity)
    total = await db.scalar(count_query) or 0
    rows = (
        await db.execute(
            query.order_by(LogEvent.timestamp.asc().nulls_last()).offset(offset).limit(limit)
        )
    ).scalars()
    return {
        "total": total,
        "offset": offset,
        "events": [LogEventOut.model_validate(e).model_dump(mode="json") for e in rows],
    }


@router.delete("/{upload_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_upload(
    upload_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    upload = await _owned_upload(db, user, upload_id)
    Path(upload.storage_path).unlink(missing_ok=True)
    await db.delete(upload)
    await db.commit()
