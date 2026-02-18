"""Tests for vector RAG: search, merge, fallback, embed_text."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import lancedb
import numpy as np
import pytest

from artifactor.chat.rag_pipeline import (
    VectorResult,
    _format_context,
    _merge_results,
    _search_vectors,
)
from artifactor.config import Settings
from artifactor.constants import EMBEDDINGS_TABLE
from artifactor.models.entity import CodeEntityRecord

# -- VectorResult dataclass --


class TestVectorResult:
    def test_creation(self) -> None:
        vr = VectorResult(
            file_path="main.py",
            symbol_name="greet",
            content="def greet():",
            start_line=1,
            end_line=5,
            distance=0.123,
        )
        assert vr.file_path == "main.py"
        assert vr.distance == 0.123

    def test_frozen(self) -> None:
        vr = VectorResult(
            file_path="a.py",
            symbol_name="",
            content="",
            start_line=1,
            end_line=1,
            distance=0.0,
        )
        with pytest.raises(AttributeError):
            vr.file_path = "b.py"  # type: ignore[misc]


# -- Merge results --


class TestMergeResults:
    def _make_entity(
        self, file_path: str, start_line: int, name: str
    ) -> CodeEntityRecord:
        return CodeEntityRecord(
            id=f"{name}-id",
            project_id="proj1",
            name=name,
            entity_type="function",
            file_path=file_path,
            start_line=start_line,
            end_line=start_line + 5,
            language="python",
        )

    def test_no_vectors_returns_entities(self) -> None:
        entities = [
            self._make_entity("a.py", 1, "foo"),
            self._make_entity("b.py", 10, "bar"),
        ]
        result = _merge_results([], entities, 10)
        assert len(result) == 2

    def test_overlap_boosted_by_rrf(self) -> None:
        vectors = [
            VectorResult(
                file_path="a.py",
                symbol_name="foo",
                content="...",
                start_line=1,
                end_line=6,
                distance=0.1,
            ),
        ]
        entities = [
            self._make_entity("a.py", 1, "foo"),
            self._make_entity("b.py", 10, "bar"),
        ]
        result = _merge_results(vectors, entities, 10)
        # RRF boosts foo (appears in both lists) — both returned
        assert len(result) == 2
        assert result[0].name == "foo"

    def test_respects_max_results(self) -> None:
        entities = [
            self._make_entity(f"f{i}.py", i, f"fn{i}")
            for i in range(20)
        ]
        result = _merge_results([], entities, 5)
        assert len(result) == 5


# -- Search vectors (with LanceDB) --


class TestSearchVectors:
    @pytest.fixture
    def settings(self, tmp_path: Any) -> Settings:
        return Settings(
            lancedb_uri=str(tmp_path / "lancedb"),
            litellm_embedding_model="text-embedding-3-small",
        )

    async def test_returns_empty_when_no_table(
        self, settings: Settings
    ) -> None:
        """Falls back when embeddings table doesn't exist."""
        db = await lancedb.connect_async(settings.lancedb_uri)
        assert (await db.list_tables()).tables == []
        with patch(
            "artifactor.chat.rag_pipeline.embed_text",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await _search_vectors("test query", settings)
        assert result == []

    async def test_returns_empty_when_embed_fails(
        self, settings: Settings
    ) -> None:
        """Falls back when embedding API fails."""
        db = await lancedb.connect_async(settings.lancedb_uri)
        dim = 8
        records = [
            {
                "vector": np.random.randn(dim).tolist(),
                "file_path": "a.py",
                "language": "python",
                "start_line": 1,
                "end_line": 10,
                "symbol_name": "foo",
                "content": "def foo(): pass",
            }
        ]
        await db.create_table(  # type: ignore[arg-type]
            EMBEDDINGS_TABLE, records
        )

        with patch(
            "artifactor.chat.rag_pipeline.embed_text",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await _search_vectors("test", settings)
        assert result == []

    async def test_returns_results_with_mock_embed(
        self, settings: Settings
    ) -> None:
        """Returns vector results when embedding succeeds."""
        dim = 8
        db = await lancedb.connect_async(settings.lancedb_uri)
        records = [
            {
                "vector": [0.1] * dim,
                "file_path": "main.py",
                "language": "python",
                "start_line": 1,
                "end_line": 10,
                "symbol_name": "Calculator",
                "content": "class Calculator: ...",
            },
            {
                "vector": [0.9] * dim,
                "file_path": "utils.js",
                "language": "javascript",
                "start_line": 1,
                "end_line": 5,
                "symbol_name": "formatDate",
                "content": "function formatDate() {}",
            },
        ]
        await db.create_table(  # type: ignore[arg-type]
            EMBEDDINGS_TABLE, records
        )

        # Mock embed_text to return a vector close to [0.1]*dim
        mock_vec = [0.1] * dim
        with patch(
            "artifactor.chat.rag_pipeline.embed_text",
            new_callable=AsyncMock,
            return_value=mock_vec,
        ):
            result = await _search_vectors("Calculator", settings)

        assert len(result) > 0
        # Closest match should be Calculator (vector [0.1]*dim)
        assert result[0].symbol_name == "Calculator"
        assert result[0].file_path == "main.py"
        assert result[0].distance >= 0.0


# -- Format context with vectors --


class TestFormatContextWithVectors:
    def test_includes_semantic_matches(self) -> None:
        vectors = [
            VectorResult(
                file_path="a.py",
                symbol_name="foo",
                content="def foo(): return 42",
                start_line=1,
                end_line=2,
                distance=0.05,
            ),
        ]
        output = _format_context([], [], vectors)
        assert "Semantic Matches" in output
        assert "foo" in output
        assert "0.050" in output

    def test_no_vectors_no_section(self) -> None:
        output = _format_context([], [], [])
        assert "Semantic Matches" not in output


# -- embed_text --


class TestEmbedText:
    async def test_returns_empty_on_failure(self) -> None:
        from artifactor.analysis.llm.embedder import embed_text

        with patch(
            "artifactor.analysis.llm.embedder._guarded_embed",
            new_callable=AsyncMock,
            side_effect=Exception("API unavailable"),
        ):
            result = await embed_text("test query")
            assert result == []
