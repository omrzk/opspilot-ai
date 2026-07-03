import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TimestampedBase


class Analysis(TimestampedBase):
    """AI analysis of an upload: root cause, affected systems, remediation, scripts."""

    __tablename__ = "analyses"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    upload_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("uploads.id", ondelete="CASCADE"), index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), default="queued", nullable=False)
    model: Mapped[str] = mapped_column(String(120), default="", nullable=False)

    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    root_cause: Mapped[str] = mapped_column(Text, default="", nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default="unknown", nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    # [{"name": "...", "role": "...", "evidence": "..."}]
    affected_systems: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    # [{"step": 1, "action": "...", "rationale": "..."}]
    remediation: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    # {"powershell": "...", "bash": "...", "terraform": "...", "ansible": "..."}
    scripts: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    # Key events cited as evidence and RAG context used
    evidence: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    error: Mapped[str] = mapped_column(Text, default="", nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
