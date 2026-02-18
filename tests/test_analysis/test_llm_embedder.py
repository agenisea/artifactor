"""Tests for the LLM embedder module."""

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from circuitbreaker import CircuitBreakerMonitor

from artifactor.analysis.llm.embedder import (
    _batch_texts,
    _truncate,
    embed_chunks,
)
from artifactor.config import Settings
from artifactor.constants import estimate_tokens
from artifactor.ingestion.schemas import CodeChunk


@pytest.fixture(autouse=True)
def _reset_breakers() -> None:
    """Reset circuit breakers between tests."""
    for cb in CircuitBreakerMonitor.get_circuits():
        cb.reset()  # type: ignore[union-attr]


def _make_chunk(content: str = "def hello():\n    pass") -> CodeChunk:
    return CodeChunk(
        file_path=Path("src/main.py"),
        language="python",
        chunk_type="function",
        start_line=1,
        end_line=2,
        content=content,
    )


def testestimate_tokens() -> None:
    assert estimate_tokens("") == 0
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("a" * 40) == 10


def test_truncate_short_text() -> None:
    """Short text passes through unchanged."""
    assert _truncate("hello world") == "hello world"


def test_truncate_long_text() -> None:
    """Text exceeding max_tokens * 4 chars is truncated."""
    text = "x" * 40_000  # 10K tokens at 4 chars/token
    result = _truncate(text, max_tokens=100)  # 100 * 4 = 400 chars
    assert len(result) == 400
    assert result == "x" * 400


def test_batch_texts_single_batch() -> None:
    """Small texts fit in a single batch."""
    texts = ["a" * 40, "b" * 40]  # 10 tokens each
    batches = _batch_texts(texts, max_batch_tokens=100)
    assert len(batches) == 1
    assert len(batches[0]) == 2


def test_batch_texts_splits_at_limit() -> None:
    """Texts exceeding batch limit are split into multiple batches."""
    texts = ["a" * 400, "b" * 400, "c" * 400]  # 100 tokens each
    batches = _batch_texts(texts, max_batch_tokens=150)
    # 100 + 100 > 150 → splits after first
    assert len(batches) >= 2
    # All original indices present
    all_indices = [idx for batch in batches for idx, _ in batch]
    assert sorted(all_indices) == [0, 1, 2]


class TestEmbedChunks:
    @pytest.mark.asyncio
    async def test_skips_tiny_chunks(self) -> None:
        tiny = _make_chunk("x")  # ~0 tokens
        result = await embed_chunks([tiny], Settings())
        assert result == 0

    @pytest.mark.asyncio
    async def test_empty_chunk_list(self) -> None:
        result = await embed_chunks([], Settings())
        assert result == 0

    @pytest.mark.asyncio
    async def test_successful_embedding(self) -> None:
        chunk = _make_chunk("def greet(name):\n    return 'hi ' + name")
        embed_data = type(
            "Item", (), {"__getitem__": lambda s, k: [0.1, 0.2, 0.3]}
        )()
        embed_response: Any = type(
            "EmbedResponse", (), {"data": [embed_data]}
        )()

        mock_table = AsyncMock()
        mock_db = AsyncMock()
        table_list = MagicMock()
        table_list.tables = ["embeddings"]
        mock_db.list_tables = AsyncMock(return_value=table_list)
        mock_db.open_table = AsyncMock(return_value=mock_table)

        with (
            patch(
                "artifactor.analysis.llm.embedder._aembedding",
                new=AsyncMock(return_value=embed_response),
            ),
            patch(
                "artifactor.analysis.llm.embedder.lancedb.connect_async",
                new=AsyncMock(return_value=mock_db),
            ),
        ):
            result = await embed_chunks([chunk], Settings())
        assert result == 1
        mock_table.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_creates_table_when_not_exists(self) -> None:
        chunk = _make_chunk("def greet(name):\n    return 'hi ' + name")
        embed_data = type(
            "Item", (), {"__getitem__": lambda s, k: [0.1, 0.2]}
        )()
        embed_response: Any = type(
            "EmbedResponse", (), {"data": [embed_data]}
        )()

        mock_db = AsyncMock()
        table_list = MagicMock()
        table_list.tables = []
        mock_db.list_tables = AsyncMock(return_value=table_list)
        mock_db.create_table = AsyncMock()

        with (
            patch(
                "artifactor.analysis.llm.embedder._aembedding",
                new=AsyncMock(return_value=embed_response),
            ),
            patch(
                "artifactor.analysis.llm.embedder.lancedb.connect_async",
                new=AsyncMock(return_value=mock_db),
            ),
        ):
            result = await embed_chunks([chunk], Settings())
        assert result == 1
        mock_db.create_table.assert_called_once()

    @pytest.mark.asyncio
    async def test_embedding_api_failure_returns_zero(self) -> None:
        chunk = _make_chunk("def greet(name):\n    return 'hi'")
        with patch(
            "artifactor.analysis.llm.embedder._aembedding",
            new=AsyncMock(side_effect=Exception("API down")),
        ):
            result = await embed_chunks([chunk], Settings())
        assert result == 0

    @pytest.mark.asyncio
    async def test_vector_count_mismatch_returns_zero(self) -> None:
        chunk = _make_chunk("def greet(name):\n    return 'hi'")
        # Return 2 vectors for 1 chunk — mismatch
        embed_data_1 = MagicMock()
        embed_data_1.__getitem__ = lambda s, k: [0.1]
        embed_data_2 = MagicMock()
        embed_data_2.__getitem__ = lambda s, k: [0.2]
        embed_response: Any = type(
            "EmbedResponse", (), {"data": [embed_data_1, embed_data_2]}
        )()
        with patch(
            "artifactor.analysis.llm.embedder._aembedding",
            new=AsyncMock(return_value=embed_response),
        ):
            result = await embed_chunks([chunk], Settings())
        assert result == 0
