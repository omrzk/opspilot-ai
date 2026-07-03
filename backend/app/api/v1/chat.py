"""AI chat with SSE streaming, RAG context and attached-upload context."""

import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.api.v1.demo import enforce_demo_chat_quota
from app.db.session import get_db
from app.models.chat import Conversation, Message
from app.models.upload import LogEvent, Upload
from app.models.user import User
from app.schemas.chat import ChatRequest, ConversationDetail, ConversationOut
from app.services.analysis.prompts import CHAT_SYSTEM_PROMPT, SOURCE_GUIDANCE
from app.services.analysis.sampler import build_digest, render_digest
from app.services.llm.base import ChatMessage
from app.services.llm.factory import build_chat_provider
from app.services.rag.retriever import format_context, retrieve

router = APIRouter(prefix="/chat", tags=["chat"])

HISTORY_LIMIT = 20
UPLOAD_CONTEXT_LIMIT = 3


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def _upload_context(db: AsyncSession, user: User, upload_ids: list[uuid.UUID]) -> str:
    blocks: list[str] = []
    for upload_id in upload_ids[:UPLOAD_CONTEXT_LIMIT]:
        upload = await db.get(Upload, upload_id)
        if upload is None or upload.user_id != user.id or upload.status != "parsed":
            continue
        events = list(
            (await db.execute(select(LogEvent).where(LogEvent.upload_id == upload.id))).scalars()
        )
        if not events:
            continue
        digest = render_digest(build_digest(events), upload.source_type)
        guidance = SOURCE_GUIDANCE.get(upload.source_type, "")
        blocks.append(f"=== UPLOADED LOG: {upload.filename} ===\n{guidance}\n\n{digest}")
    return "\n\n".join(blocks)


@router.post("")
async def chat(
    payload: ChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    await enforce_demo_chat_quota(db, user)
    if payload.conversation_id is not None:
        conversation = await db.get(Conversation, payload.conversation_id)
        if conversation is None or conversation.user_id != user.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    else:
        conversation = Conversation(user_id=user.id, title=payload.message[:80])
        db.add(conversation)
        await db.flush()

    db.add(Message(conversation_id=conversation.id, role="user", content=payload.message))
    await db.commit()

    history = list(
        (
            await db.execute(
                select(Message)
                .where(Message.conversation_id == conversation.id)
                .order_by(Message.created_at.desc())
                .limit(HISTORY_LIMIT)
            )
        ).scalars()
    )[::-1]

    # Assemble context
    sources_meta: list[dict] = []
    system_parts = [CHAT_SYSTEM_PROMPT]
    if payload.use_rag:
        chunks = await retrieve(db, user_id=user.id, query=payload.message)
        if chunks:
            system_parts.append(
                "Relevant knowledge base context:\n\n" + format_context(chunks)
            )
            sources_meta = [
                {"title": c.document_title, "doc_type": c.doc_type, "score": round(c.score, 3)}
                for c in chunks
            ]
    if payload.upload_ids:
        upload_block = await _upload_context(db, user, payload.upload_ids)
        if upload_block:
            system_parts.append(upload_block)

    messages = [ChatMessage("system", "\n\n".join(system_parts))] + [
        ChatMessage(m.role, m.content) for m in history if m.role in ("user", "assistant")
    ]

    provider = build_chat_provider()
    conversation_id = conversation.id

    async def event_stream():
        yield _sse(
            "meta",
            {
                "conversation_id": str(conversation_id),
                "model": provider.model,
                "sources": sources_meta,
            },
        )
        collected: list[str] = []
        try:
            async for delta in provider.stream(messages):
                collected.append(delta)
                yield _sse("delta", {"text": delta})
        except Exception as exc:
            yield _sse("error", {"detail": f"{type(exc).__name__}: {exc}"})
            return
        full_text = "".join(collected)
        message_id = None
        if full_text:
            assistant = Message(
                conversation_id=conversation_id,
                role="assistant",
                content=full_text,
                meta={"model": provider.model, "sources": sources_meta},
            )
            db.add(assistant)
            await db.commit()
            message_id = str(assistant.id)
        yield _sse("done", {"message_id": message_id})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/conversations", response_model=list[ConversationOut])
async def list_conversations(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[ConversationOut]:
    rows = (
        await db.execute(
            select(Conversation)
            .where(Conversation.user_id == user.id)
            .order_by(Conversation.updated_at.desc())
            .limit(100)
        )
    ).scalars()
    return [ConversationOut.model_validate(c) for c in rows]


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationDetail:
    conversation = await db.scalar(
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(Conversation.id == conversation_id, Conversation.user_id == user.id)
    )
    if conversation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    return ConversationDetail.model_validate(conversation)


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    conversation = await db.get(Conversation, conversation_id)
    if conversation is None or conversation.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    await db.delete(conversation)
    await db.commit()
