"""Semantic retrieval over document_chunks via pgvector cosine distance."""

import logging
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.knowledge import Document, DocumentChunk
from app.services.llm.factory import build_embedding_provider

logger = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    document_id: uuid.UUID
    document_title: str
    doc_type: str
    content: str
    score: float  # cosine similarity in [0, 1]


async def retrieve(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    query: str,
    top_k: int | None = None,
) -> list[RetrievedChunk]:
    """Return the user's most relevant knowledge-base chunks for a query.

    Fails soft: if the embedding provider is unreachable, returns [] so chat
    and analysis still work without RAG context."""
    settings = get_settings()
    try:
        vectors = await build_embedding_provider(settings).embed([query])
    except Exception:
        logger.warning("Embedding provider unavailable; skipping RAG retrieval", exc_info=True)
        return []
    if not vectors:
        return []
    query_vector = vectors[0]

    distance = DocumentChunk.embedding.cosine_distance(query_vector)
    stmt = (
        select(DocumentChunk.content, Document.id, Document.title, Document.doc_type, distance)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(Document.user_id == user_id, DocumentChunk.embedding.is_not(None))
        .order_by(distance)
        .limit(top_k or settings.rag_top_k)
    )
    rows = (await db.execute(stmt)).all()
    return [
        RetrievedChunk(
            document_id=doc_id,
            document_title=title,
            doc_type=doc_type,
            content=content,
            score=max(0.0, 1.0 - float(dist)),
        )
        for content, doc_id, title, doc_type, dist in rows
    ]


def format_context(chunks: list[RetrievedChunk]) -> str:
    """Render retrieved chunks as a context block for prompts."""
    if not chunks:
        return ""
    sections = [
        f"[Source: {c.document_title} ({c.doc_type}), relevance {c.score:.2f}]\n{c.content}"
        for c in chunks
    ]
    return "\n\n---\n\n".join(sections)
