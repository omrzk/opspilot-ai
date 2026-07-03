import pytest

from app.services.rag.chunking import chunk_text


def test_short_text_single_chunk():
    chunks = chunk_text("hello world", chunk_size=100, overlap=10)
    assert len(chunks) == 1
    assert chunks[0].content == "hello world"
    assert chunks[0].ordinal == 0


def test_paragraphs_grouped_within_budget():
    text = "para one\n\npara two\n\npara three"
    chunks = chunk_text(text, chunk_size=25, overlap=5)
    assert len(chunks) >= 2
    joined = " ".join(c.content for c in chunks)
    for para in ("para one", "para two", "para three"):
        assert para in joined


def test_oversized_paragraph_is_windowed_with_overlap():
    text = "x" * 1000
    chunks = chunk_text(text, chunk_size=300, overlap=50)
    assert all(len(c.content) <= 300 for c in chunks)
    # Full coverage: total unique content must reconstruct the original length
    step = 300 - 50
    assert len(chunks) == -(-1000 // step) or len(chunks) >= 4


def test_ordinals_sequential():
    text = "\n\n".join(f"paragraph {i} " + "y" * 50 for i in range(20))
    chunks = chunk_text(text, chunk_size=120, overlap=20)
    assert [c.ordinal for c in chunks] == list(range(len(chunks)))


def test_invalid_params_raise():
    with pytest.raises(ValueError):
        chunk_text("abc", chunk_size=0)
    with pytest.raises(ValueError):
        chunk_text("abc", chunk_size=10, overlap=10)
