import uuid
from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import TimestampedBase


class Upload(TimestampedBase):
    """A file uploaded for analysis (EVTX/JSON/TXT/CSV/XML)."""

    __tablename__ = "uploads"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    # Detected log source: windows_event | sysmon | defender | azure | vmware |
    # cloudtrail | kubernetes | syslog | generic
    source_type: Mapped[str] = mapped_column(String(40), default="unknown", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    record_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error: Mapped[str] = mapped_column(Text, default="", nullable=False)

    events: Mapped[list["LogEvent"]] = relationship(
        back_populates="upload", cascade="all, delete-orphan"
    )


class LogEvent(TimestampedBase):
    """A normalized event extracted from an upload."""

    __tablename__ = "log_events"

    upload_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("uploads.id", ondelete="CASCADE"), index=True, nullable=False
    )
    timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source: Mapped[str] = mapped_column(String(40), default="generic", nullable=False)
    host: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default="info", nullable=False)
    event_id: Mapped[str] = mapped_column(String(60), default="", nullable=False)
    message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    raw: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    upload: Mapped[Upload] = relationship(back_populates="events")
