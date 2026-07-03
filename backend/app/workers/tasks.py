"""Celery tasks: parsing, analysis, report generation, knowledge ingestion."""

import asyncio
import logging
import uuid
from pathlib import Path

from app.models.upload import LogEvent, Upload
from app.services.analysis.engine import run_analysis
from app.services.parsers.service import parse_file
from app.services.rag.ingest import ingest_document
from app.services.reports.generator import run_report
from app.workers.celery_app import celery_app
from app.workers.db import task_session

logger = logging.getLogger(__name__)

EVENT_INSERT_BATCH = 500


async def _parse_upload(upload_id: uuid.UUID) -> None:
    async with task_session() as db:
        upload = await db.get(Upload, upload_id)
        if upload is None:
            logger.error("Upload %s not found", upload_id)
            return
        upload.status = "parsing"
        await db.commit()
        try:
            result = parse_file(Path(upload.storage_path), upload.filename)
            for start in range(0, len(result.events), EVENT_INSERT_BATCH):
                for event in result.events[start : start + EVENT_INSERT_BATCH]:
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
                await db.flush()
            upload.source_type = result.source_type
            upload.record_count = len(result.events)
            upload.error = "; ".join(result.warnings)
            upload.status = "parsed"
            await db.commit()
        except Exception as exc:
            logger.exception("Parsing upload %s failed", upload_id)
            await db.rollback()
            upload = await db.get(Upload, upload_id)
            if upload is not None:
                upload.status = "failed"
                upload.error = f"{type(exc).__name__}: {exc}"[:2000]
                await db.commit()


@celery_app.task(name="opspilot.parse_upload")
def parse_upload_task(upload_id: str) -> None:
    asyncio.run(_parse_upload(uuid.UUID(upload_id)))


@celery_app.task(name="opspilot.analyze")
def analyze_task(analysis_id: str, instructions: str = "") -> None:
    async def _run() -> None:
        async with task_session() as db:
            await run_analysis(db, uuid.UUID(analysis_id), instructions)

    asyncio.run(_run())


@celery_app.task(name="opspilot.generate_report")
def generate_report_task(report_id: str, instructions: str = "") -> None:
    async def _run() -> None:
        async with task_session() as db:
            await run_report(db, uuid.UUID(report_id), instructions)

    asyncio.run(_run())


@celery_app.task(name="opspilot.ingest_document")
def ingest_document_task(
    user_id: str, title: str, text: str, doc_type: str = "documentation", source: str = ""
) -> None:
    async def _run() -> None:
        async with task_session() as db:
            await ingest_document(
                db,
                user_id=uuid.UUID(user_id),
                title=title,
                text=text,
                doc_type=doc_type,
                source=source,
            )

    asyncio.run(_run())
