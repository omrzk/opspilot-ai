"""Root-cause analysis engine: events -> digest -> RAG -> LLM -> structured result."""

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import utcnow
from app.models.analysis import Analysis
from app.models.upload import LogEvent, Upload
from app.services.analysis.prompts import (
    ANALYSIS_SYSTEM_PROMPT,
    build_analysis_user_prompt,
)
from app.services.analysis.sampler import build_digest, render_digest
from app.services.llm.base import ChatMessage
from app.services.llm.factory import build_chat_provider
from app.services.llm.json_utils import extract_json_object
from app.services.rag.retriever import format_context, retrieve

logger = logging.getLogger(__name__)

VALID_SEVERITIES = {"critical", "high", "medium", "low", "informational"}
SCRIPT_KEYS = ("powershell", "bash", "terraform", "ansible")


def _coerce_result(parsed: dict) -> dict:
    """Validate and normalize the LLM's JSON so bad output can't corrupt the DB."""
    confidence = parsed.get("confidence", 0.0)
    try:
        confidence = max(0.0, min(1.0, float(confidence)))
    except (TypeError, ValueError):
        confidence = 0.0

    severity = str(parsed.get("severity", "medium")).lower()
    if severity not in VALID_SEVERITIES:
        severity = "medium"

    def _str_list(value) -> list:
        if not isinstance(value, list):
            return []
        return [str(v) for v in value if v]

    def _dict_list(value, required_key: str) -> list:
        if not isinstance(value, list):
            return []
        return [v for v in value if isinstance(v, dict) and v.get(required_key)]

    scripts_raw = parsed.get("scripts") or {}
    scripts = {}
    if isinstance(scripts_raw, dict):
        for key in SCRIPT_KEYS:
            value = scripts_raw.get(key, "")
            scripts[key] = value if isinstance(value, str) else ""

    evidence = _str_list(parsed.get("evidence"))
    alternatives = _str_list(parsed.get("alternative_hypotheses"))
    if alternatives:
        evidence = evidence + [f"Alternative hypothesis: {a}" for a in alternatives]

    return {
        "summary": str(parsed.get("summary", "")),
        "root_cause": str(parsed.get("root_cause", "")),
        "severity": severity,
        "confidence": confidence,
        "affected_systems": _dict_list(parsed.get("affected_systems"), "name"),
        "remediation": _dict_list(parsed.get("remediation"), "action"),
        "scripts": scripts,
        "evidence": evidence,
    }


async def run_analysis(db: AsyncSession, analysis_id: uuid.UUID, instructions: str = "") -> None:
    """Execute one analysis end-to-end. Persists success or failure on the row."""
    analysis = await db.get(Analysis, analysis_id)
    if analysis is None:
        logger.error("Analysis %s not found", analysis_id)
        return
    analysis.status = "running"
    await db.commit()

    try:
        upload = await db.get(Upload, analysis.upload_id)
        if upload is None:
            raise RuntimeError("Upload no longer exists")
        events = list(
            (await db.execute(select(LogEvent).where(LogEvent.upload_id == upload.id))).scalars()
        )
        if not events:
            raise RuntimeError("Upload has no parsed events to analyze")

        digest = build_digest(events)
        digest_text = render_digest(digest, upload.source_type)

        # Pull related runbooks / past incidents from the knowledge base
        rag_query = f"{upload.source_type} incident: " + " ".join(
            e.message[:120] for e in digest.sampled[:5]
        )
        chunks = await retrieve(db, user_id=analysis.user_id, query=rag_query)
        rag_context = format_context(chunks)

        provider = build_chat_provider()
        result = await provider.chat(
            [
                ChatMessage("system", ANALYSIS_SYSTEM_PROMPT),
                ChatMessage(
                    "user",
                    build_analysis_user_prompt(
                        digest_text, upload.source_type, rag_context, instructions
                    ),
                ),
            ],
            temperature=0.1,
            max_tokens=8192,
        )
        coerced = _coerce_result(extract_json_object(result.text))

        analysis.model = result.model
        analysis.summary = coerced["summary"]
        analysis.root_cause = coerced["root_cause"]
        analysis.severity = coerced["severity"]
        analysis.confidence = coerced["confidence"]
        analysis.affected_systems = coerced["affected_systems"]
        analysis.remediation = coerced["remediation"]
        analysis.scripts = coerced["scripts"]
        analysis.evidence = coerced["evidence"]
        analysis.status = "completed"
        analysis.completed_at = utcnow()
        await db.commit()
        logger.info("Analysis %s completed (confidence %.2f)", analysis_id, analysis.confidence)
    except Exception as exc:
        logger.exception("Analysis %s failed", analysis_id)
        await db.rollback()
        analysis = await db.get(Analysis, analysis_id)
        if analysis is not None:
            analysis.status = "failed"
            analysis.error = f"{type(exc).__name__}: {exc}"[:2000]
            await db.commit()
