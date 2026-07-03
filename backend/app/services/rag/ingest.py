"""Ingest text into the knowledge base: chunk, embed, store."""

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.knowledge import Document, DocumentChunk
from app.services.llm.factory import build_embedding_provider
from app.services.rag.chunking import chunk_text

logger = logging.getLogger(__name__)

EMBED_BATCH_SIZE = 32


async def ingest_document(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    title: str,
    text: str,
    doc_type: str = "documentation",
    source: str = "",
) -> Document:
    """Create a Document with embedded chunks. Commits on success."""
    settings = get_settings()
    doc = Document(
        user_id=user_id, title=title, doc_type=doc_type, source=source, status="processing"
    )
    db.add(doc)
    await db.flush()

    chunks = chunk_text(text, settings.rag_chunk_size, settings.rag_chunk_overlap)
    provider = build_embedding_provider(settings)

    for start in range(0, len(chunks), EMBED_BATCH_SIZE):
        batch = chunks[start : start + EMBED_BATCH_SIZE]
        vectors = await provider.embed([c.content for c in batch])
        if len(vectors) != len(batch):
            raise RuntimeError(
                f"Embedding provider returned {len(vectors)} vectors for {len(batch)} inputs"
            )
        for chunk, vector in zip(batch, vectors, strict=True):
            db.add(
                DocumentChunk(
                    document_id=doc.id,
                    ordinal=chunk.ordinal,
                    content=chunk.content,
                    embedding=vector,
                )
            )

    doc.status = "ready"
    await db.commit()
    await db.refresh(doc)
    logger.info("Ingested document %s (%d chunks)", doc.id, len(chunks))
    return doc
