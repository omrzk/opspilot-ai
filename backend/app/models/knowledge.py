"""Knowledge base: documents and pgvector-embedded chunks for RAG."""

import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import get_settings
from app.db.base import TimestampedBase

_EMBEDDING_DIM = get_settings().embedding_dim


class Document(TimestampedBase):
    __tablename__ = "documents"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    # runbook | documentation | incident_history | upload | note
    doc_type: Mapped[str] = mapped_column(String(40), default="documentation", nullable=False)
    source: Mapped[str] = mapped_column(String(1024), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)

    chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class DocumentChunk(TimestampedBase):
    __tablename__ = "document_chunks"

    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=False
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(_EMBEDDING_DIM), nullable=True)

    document: Mapped[Document] = relationship(back_populates="chunks")
