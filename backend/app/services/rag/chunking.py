"""Text chunking for embedding: paragraph-aware sliding window with overlap."""

from dataclasses import dataclass


@dataclass
class Chunk:
    ordinal: int
    content: str


def _split_paragraphs(text: str) -> list[str]:
    parts = [p.strip() for p in text.replace("\r\n", "\n").split("\n\n")]
    return [p for p in parts if p]


def chunk_text(text: str, chunk_size: int = 1200, overlap: int = 150) -> list[Chunk]:
    """Split text into ~chunk_size character chunks.

    Prefers paragraph boundaries; falls back to a hard character window with
    overlap for oversized paragraphs so no content is ever dropped."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be in [0, chunk_size)")

    chunks: list[str] = []
    buffer = ""
    for para in _split_paragraphs(text):
        if len(para) > chunk_size:
            if buffer:
                chunks.append(buffer)
                buffer = ""
            step = chunk_size - overlap
            for start in range(0, len(para), step):
                piece = para[start : start + chunk_size]
                chunks.append(piece)
                if start + chunk_size >= len(para):
                    break
            continue
        if buffer and len(buffer) + len(para) + 2 > chunk_size:
            chunks.append(buffer)
            buffer = para
        else:
            buffer = f"{buffer}\n\n{para}" if buffer else para
    if buffer:
        chunks.append(buffer)

    return [Chunk(ordinal=i, content=c) for i, c in enumerate(chunks)]
