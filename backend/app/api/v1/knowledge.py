"""Knowledge base: ingest documents for RAG, semantic search."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.knowledge import Document, DocumentChunk
from app.models.user import User
from app.services.rag.retriever import retrieve
from app.workers.tasks import ingest_document_task

router = APIRouter(prefix="/knowledge", tags=["knowledge"])

DOC_TYPES = {"runbook", "documentation", "incident_history", "note"}


class DocumentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=512)
    text: str = Field(min_length=1, max_length=2_000_000)
    doc_type: str = "documentation"
    source: str = ""


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    doc_type: str
    source: str
    status: str


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=10_000)
    top_k: int = Field(default=6, ge=1, le=20)


@router.post("/documents", status_code=status.HTTP_202_ACCEPTED)
async def create_document(
    payload: DocumentCreate,
    user: User = Depends(get_current_user),
) -> dict:
    if payload.doc_type not in DOC_TYPES:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"doc_type must be one of {sorted(DOC_TYPES)}",
        )
    ingest_document_task.delay(
        str(user.id), payload.title, payload.text, payload.doc_type, payload.source
    )
    return {"status": "queued", "title": payload.title}


@router.get("/documents", response_model=list[DocumentOut])
async def list_documents(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[DocumentOut]:
    rows = (
        await db.execute(
            select(Document).where(Document.user_id == user.id).order_by(Document.created_at.desc())
        )
    ).scalars()
    return [DocumentOut.model_validate(d) for d in rows]


@router.get("/documents/{document_id}/stats")
async def document_stats(
    document_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    document = await db.get(Document, document_id)
    if document is None or document.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    chunk_count = await db.scalar(
        select(func.count(DocumentChunk.id)).where(DocumentChunk.document_id == document.id)
    )
    return {"id": str(document.id), "title": document.title, "chunks": chunk_count or 0}


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    document = await db.get(Document, document_id)
    if document is None or document.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    await db.delete(document)
    await db.commit()


@router.post("/search")
async def search(
    payload: SearchRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    chunks = await retrieve(db, user_id=user.id, query=payload.query, top_k=payload.top_k)
    return {
        "query": payload.query,
        "results": [
            {
                "document_id": str(c.document_id),
                "title": c.document_title,
                "doc_type": c.doc_type,
                "score": round(c.score, 4),
                "content": c.content,
            }
            for c in chunks
        ],
    }
