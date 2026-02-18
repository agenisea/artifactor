"""Tests for typed emitter convenience functions."""

from __future__ import annotations

import pytest

from artifactor.observability.dispatcher import TraceDispatcher
from artifactor.observability.emitters import (
    emit_error,
    emit_llm_call,
    emit_pipeline_end,
    emit_pipeline_start,
    emit_stage_end,
    emit_stage_start,
)
from artifactor.observability.events import TraceEvent


class _Collector:
    """Test handler that collects events."""

    def __init__(self) -> None:
        self.events: list[TraceEvent] = []

    @property
    def name(self) -> str:
        return "collector"

    async def handle(self, event: TraceEvent) -> None:
        self.events.append(event)


@pytest.fixture
def dispatcher() -> tuple[TraceDispatcher, _Collector]:
    d = TraceDispatcher()
    c = _Collector()
    d.register(c)
    return d, c


class TestEmitters:
    @pytest.mark.asyncio
    async def test_emit_pipeline_start(
        self, dispatcher: tuple[TraceDispatcher, _Collector]
    ) -> None:
        d, c = dispatcher
        await emit_pipeline_start(d, "trace1", "proj1")
        assert len(c.events) == 1
        assert c.events[0].type == "pipeline_start"
        assert c.events[0].data["project_id"] == "proj1"

    @pytest.mark.asyncio
    async def test_emit_pipeline_end(
        self, dispatcher: tuple[TraceDispatcher, _Collector]
    ) -> None:
        d, c = dispatcher
        await emit_pipeline_end(
            d, "trace1", 1234.5, success=True
        )
        assert len(c.events) == 1
        assert c.events[0].type == "pipeline_end"
        assert c.events[0].data["duration_ms"] == 1234.5
        assert c.events[0].data["success"] is True

    @pytest.mark.asyncio
    async def test_emit_stage_start(
        self, dispatcher: tuple[TraceDispatcher, _Collector]
    ) -> None:
        d, c = dispatcher
        await emit_stage_start(
            d, "trace1", "static_analysis", category="analysis"
        )
        assert c.events[0].type == "stage_start"
        assert c.events[0].data["stage"] == "static_analysis"
        assert c.events[0].category == "analysis"

    @pytest.mark.asyncio
    async def test_emit_stage_end(
        self, dispatcher: tuple[TraceDispatcher, _Collector]
    ) -> None:
        d, c = dispatcher
        await emit_stage_end(
            d,
            "trace1",
            "static_analysis",
            500.0,
            ok=True,
        )
        assert c.events[0].type == "stage_end"
        assert c.events[0].data["ok"] is True

    @pytest.mark.asyncio
    async def test_emit_stage_end_with_error(
        self, dispatcher: tuple[TraceDispatcher, _Collector]
    ) -> None:
        d, c = dispatcher
        await emit_stage_end(
            d,
            "trace1",
            "llm_analysis",
            0.0,
            ok=False,
            error="timeout",
        )
        assert c.events[0].data["ok"] is False
        assert c.events[0].data["error"] == "timeout"

    @pytest.mark.asyncio
    async def test_emit_llm_call(
        self, dispatcher: tuple[TraceDispatcher, _Collector]
    ) -> None:
        d, c = dispatcher
        await emit_llm_call(
            d,
            "trace1",
            model="claude-sonnet",
            input_tokens=100,
            output_tokens=200,
            duration_ms=1500.0,
            cost=0.003,
        )
        assert c.events[0].type == "llm_call"
        assert c.events[0].category == "llm"
        assert c.events[0].data["model"] == "claude-sonnet"
        assert c.events[0].data["input_tokens"] == 100

    @pytest.mark.asyncio
    async def test_emit_error(
        self, dispatcher: tuple[TraceDispatcher, _Collector]
    ) -> None:
        d, c = dispatcher
        await emit_error(
            d, "trace1", "embedder", "API timeout"
        )
        assert c.events[0].type == "error"
        assert c.events[0].data["component"] == "embedder"
        assert c.events[0].data["message"] == "API timeout"
