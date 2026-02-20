"""Tests for extracted chat.py helper functions."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from artifactor.api.routes.chat import (
    _build_rag_prompt,
    _error_to_sse_event,
)
from artifactor.constants import SSEEvent


class TestBuildRagPrompt:
    @pytest.mark.asyncio
    async def test_returns_original_on_retrieval_failure(
        self,
    ) -> None:
        """When RAG retrieval raises, return the original message."""
        repos = AsyncMock()
        with patch(
            "artifactor.api.routes.chat.retrieve_context",
            new_callable=AsyncMock,
            side_effect=RuntimeError("vector store down"),
        ):
            result = await _build_rag_prompt(
                "What is Calculator?",
                "proj-1",
                repos,
                None,
            )
        assert result == "What is Calculator?"

    @pytest.mark.asyncio
    async def test_augments_with_context(self) -> None:
        """When RAG retrieval succeeds, prepend context."""
        repos = AsyncMock()
        mock_context = AsyncMock()
        mock_context.formatted = "Entity: Calculator"
        with patch(
            "artifactor.api.routes.chat.retrieve_context",
            new_callable=AsyncMock,
            return_value=mock_context,
        ):
            result = await _build_rag_prompt(
                "What is Calculator?",
                "proj-1",
                repos,
                None,
            )
        assert "Entity: Calculator" in result
        assert "Question: What is Calculator?" in result

    @pytest.mark.asyncio
    async def test_returns_original_when_no_context(
        self,
    ) -> None:
        """When RAG returns empty context, return original."""
        repos = AsyncMock()
        mock_context = AsyncMock()
        mock_context.formatted = ""
        with patch(
            "artifactor.api.routes.chat.retrieve_context",
            new_callable=AsyncMock,
            return_value=mock_context,
        ):
            result = await _build_rag_prompt(
                "Hello", "proj-1", repos, None
            )
        assert result == "Hello"


class TestErrorToSseEvent:
    def test_timeout_error(self) -> None:
        """TimeoutError maps to timeout class."""
        exc = TimeoutError()
        event = _error_to_sse_event(exc, "req-1")
        assert event["event"] == SSEEvent.ERROR
        data = json.loads(event["data"])
        assert "timed out" in data["error"]
        assert data["error_class"] == "timeout"
        assert data["request_id"] == "req-1"

    def test_generic_error(self) -> None:
        """Generic RuntimeError maps to server class."""
        exc = RuntimeError("something broke")
        event = _error_to_sse_event(exc, "req-2")
        data = json.loads(event["data"])
        assert "Chat request failed" in data["error"]
        assert data["request_id"] == "req-2"

    def test_does_not_leak_exception_details(self) -> None:
        """Error message must not contain exception text."""
        exc = RuntimeError(
            "secret /app/data/db.sqlite path"
        )
        event = _error_to_sse_event(exc, "req-3")
        data = json.loads(event["data"])
        assert "secret" not in data["error"]
        assert "/app/data" not in data["error"]
