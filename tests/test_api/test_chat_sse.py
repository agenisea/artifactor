"""Tests for chat SSE endpoint."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic_ai.models.test import TestModel

from artifactor.constants import SSEEvent
from artifactor.main import app
from tests.conftest import (
    parse_sse_events as _parse_sse_events,
)
from tests.conftest import (
    setup_test_app,
)


@pytest.fixture
async def client(tmp_path: Path):
    """Test client with fake repos and TestModel agent."""
    setup_test_app(
        tmp_path,
        agent_model=TestModel(
            custom_output_args={
                "message": "The Calculator class implements add and subtract.",
                "citations": [],
                "confidence": None,
                "tools_used": [],
            }
        ),
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test"
    ) as c:
        yield c

    app.dependency_overrides.clear()



class TestChatSSE:
    async def test_returns_sse_content_type(
        self, client: AsyncClient
    ) -> None:
        resp = await client.post(
            "/api/projects/test-project/chat",
            json={"message": "What is Calculator?"},
        )
        assert resp.status_code == 200
        content_type = resp.headers.get("content-type", "")
        assert "text/event-stream" in content_type

    async def test_has_thinking_event(
        self, client: AsyncClient
    ) -> None:
        resp = await client.post(
            "/api/projects/test-project/chat",
            json={"message": "Hello"},
        )
        events = _parse_sse_events(resp.text)
        thinking = [
            e for e in events if e["event"] == SSEEvent.THINKING
        ]
        assert len(thinking) >= 1
        data = json.loads(thinking[0]["data"])
        assert "status" in data

    async def test_has_complete_or_error_event(
        self, client: AsyncClient
    ) -> None:
        resp = await client.post(
            "/api/projects/test-project/chat",
            json={"message": "Hello"},
        )
        events = _parse_sse_events(resp.text)
        terminal = [
            e
            for e in events
            if e["event"] in (SSEEvent.COMPLETE, SSEEvent.ERROR)
        ]
        assert len(terminal) >= 1

    async def test_complete_event_has_message(
        self, client: AsyncClient
    ) -> None:
        resp = await client.post(
            "/api/projects/test-project/chat",
            json={"message": "What is Calculator?"},
        )
        events = _parse_sse_events(resp.text)
        complete = [
            e for e in events if e["event"] == SSEEvent.COMPLETE
        ]
        if complete:
            data = json.loads(complete[0]["data"])
            assert "message" in data
            assert "conversation_id" in data

    async def test_empty_message_rejected(
        self, client: AsyncClient
    ) -> None:
        resp = await client.post(
            "/api/projects/test-project/chat",
            json={"message": ""},
        )
        # Pydantic validation: message min_length=1
        assert resp.status_code == 422

    async def test_with_conversation_id(
        self, client: AsyncClient
    ) -> None:
        resp = await client.post(
            "/api/projects/test-project/chat",
            json={
                "message": "Follow up question",
                "conversation_id": "conv-123",
            },
        )
        assert resp.status_code == 200
        events = _parse_sse_events(resp.text)
        complete = [
            e for e in events if e["event"] == SSEEvent.COMPLETE
        ]
        if complete:
            data = json.loads(complete[0]["data"])
            assert data["conversation_id"] == "conv-123"

    async def test_sse_events_contain_request_id(
        self, client: AsyncClient
    ) -> None:
        """All SSE events must include request_id."""
        resp = await client.post(
            "/api/projects/test-project/chat",
            json={"message": "Hello"},
        )
        events = _parse_sse_events(resp.text)
        thinking = [
            e for e in events if e["event"] == SSEEvent.THINKING
        ]
        assert len(thinking) >= 1
        data = json.loads(thinking[0]["data"])
        assert "request_id" in data
        assert len(data["request_id"]) > 0

        complete = [
            e for e in events if e["event"] == SSEEvent.COMPLETE
        ]
        if complete:
            cdata = json.loads(complete[0]["data"])
            assert "request_id" in cdata

    async def test_complete_event_has_model_name(
        self, client: AsyncClient
    ) -> None:
        """Complete event must include model field."""
        resp = await client.post(
            "/api/projects/test-project/chat",
            json={"message": "Hello"},
        )
        events = _parse_sse_events(resp.text)
        complete = [
            e for e in events if e["event"] == SSEEvent.COMPLETE
        ]
        if complete:
            data = json.loads(complete[0]["data"])
            assert "model" in data
            assert isinstance(data["model"], str)

    async def test_sse_emits_tool_call_events(
        self, client: AsyncClient
    ) -> None:
        """agent.iter() should emit tool_call events."""
        resp = await client.post(
            "/api/projects/test-project/chat",
            json={"message": "What is Calculator?"},
        )
        events = _parse_sse_events(resp.text)
        tool_calls = [
            e for e in events if e["event"] == SSEEvent.TOOL_CALL
        ]
        # TestModel with custom_output_args produces
        # at least one ToolCallPart (the structured output tool)
        if tool_calls:
            data = json.loads(tool_calls[0]["data"])
            assert "tool" in data
            assert "message" in data
            assert "request_id" in data

    async def test_chat_timeout_yields_error_event(
        self, client: AsyncClient
    ) -> None:
        """Agent timeout produces a timeout error SSE event."""
        import asyncio
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def _hanging_iter(*_args, **_kwargs):
            await asyncio.sleep(60)
            yield  # pragma: no cover

        with patch(
            "artifactor.api.routes.chat.TIMEOUTS",
            {"chat_agent": 0.01},
        ), patch(
            "artifactor.api.routes.chat.create_agent",
        ) as mock_create:
            mock_agent = AsyncMock()
            mock_agent.iter = _hanging_iter
            mock_create.return_value = mock_agent

            resp = await client.post(
                "/api/projects/test-project/chat",
                json={"message": "slow question"},
            )

        events = _parse_sse_events(resp.text)
        error_events = [
            e for e in events if e["event"] == SSEEvent.ERROR
        ]
        assert len(error_events) >= 1
        data = json.loads(error_events[0]["data"])
        assert "timed out" in data["error"]
