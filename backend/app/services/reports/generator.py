"""Report generation: assemble analysis/incident context and have the LLM write
the requested document type."""

import json
import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analysis import Analysis
from app.models.incident import Incident
from app.models.report import Report
from app.models.upload import Upload
from app.services.analysis.prompts import REPORT_PROMPTS, REPORT_SYSTEM_PROMPT
from app.services.llm.base import ChatMessage
from app.services.llm.factory import build_chat_provider

logger = logging.getLogger(__name__)


def _analysis_context(analysis: Analysis, upload: Upload | None) -> str:
    payload = {
        "log_source": upload.source_type if upload else "unknown",
        "log_file": upload.filename if upload else "unknown",
        "event_count": upload.record_count if upload else 0,
        "analyzed_at": analysis.completed_at.isoformat() if analysis.completed_at else None,
        "summary": analysis.summary,
        "root_cause": analysis.root_cause,
        "severity": analysis.severity,
        "confidence": analysis.confidence,
        "affected_systems": analysis.affected_systems,
        "remediation": analysis.remediation,
        "scripts": analysis.scripts,
        "evidence": analysis.evidence,
    }
    return json.dumps(payload, indent=2, default=str)


def _incident_context(incident: Incident) -> str:
    payload = {
        "title": incident.title,
        "description": incident.description,
        "severity": incident.severity,
        "status": incident.status,
        "opened_at": incident.created_at.isoformat(),
        "resolved_at": incident.resolved_at.isoformat() if incident.resolved_at else None,
    }
    return json.dumps(payload, indent=2, default=str)


async def run_report(db: AsyncSession, report_id: uuid.UUID, instructions: str = "") -> None:
    report = await db.get(Report, report_id)
    if report is None:
        logger.error("Report %s not found", report_id)
        return
    report.status = "running"
    await db.commit()

    try:
        kind_prompt = REPORT_PROMPTS.get(report.kind)
        if kind_prompt is None:
            raise RuntimeError(f"Unknown report kind: {report.kind}")

        context_blocks: list[str] = []
        if report.analysis_id:
            analysis = await db.get(Analysis, report.analysis_id)
            if analysis is None or analysis.status != "completed":
                raise RuntimeError("Linked analysis is missing or not completed")
            upload = await db.get(Upload, analysis.upload_id)
            context_blocks.append("=== ANALYSIS ===\n" + _analysis_context(analysis, upload))
        if report.incident_id:
            incident = await db.get(Incident, report.incident_id)
            if incident is not None:
                context_blocks.append("=== INCIDENT ===\n" + _incident_context(incident))
        if not context_blocks:
            raise RuntimeError("Report needs an analysis_id or incident_id for context")

        user_prompt = "\n\n".join(
            [kind_prompt, *context_blocks]
            + ([f"Additional instructions: {instructions}"] if instructions else [])
        )
        provider = build_chat_provider()
        result = await provider.chat(
            [ChatMessage("system", REPORT_SYSTEM_PROMPT), ChatMessage("user", user_prompt)],
            temperature=0.3,
            max_tokens=8192,
        )
        content = result.text.strip()
        if not content:
            raise RuntimeError("LLM returned an empty report")

        report.content_md = content
        if not report.title:
            first_line = content.splitlines()[0].lstrip("# ").strip()
            report.title = first_line[:300] or report.kind.replace("_", " ").title()
        report.status = "completed"
        await db.commit()
        logger.info("Report %s (%s) completed", report_id, report.kind)
    except Exception as exc:
        logger.exception("Report %s failed", report_id)
        await db.rollback()
        report = await db.get(Report, report_id)
        if report is not None:
            report.status = "failed"
            report.error = f"{type(exc).__name__}: {exc}"[:2000]
            await db.commit()
