"""Tests for built-in trace handlers."""

from __future__ import annotations

import pytest

from artifactor.observability.events import TraceEvent
from artifactor.observability.handlers.console import (
    ConsoleTraceHandler,
)
from artifactor.observability.handlers.cost_aggregator import (
    CostAggregatorHandler,
    TraceCost,
)
from artifactor.observability.handlers.otel import OtelTraceHandler


class TestConsoleTraceHandler:
    def test_name(self) -> None:
        handler = ConsoleTraceHandler()
        assert handler.name == "console"

    @pytest.mark.asyncio
    async def test_handle_logs_event(self) -> None:
        """Handler doesn't raise on valid event."""
        handler = ConsoleTraceHandler()
        event = TraceEvent(
            type="pipeline_start",
            trace_id="t1",
            data={"project_id": "proj1"},
        )
        await handler.handle(event)


class TestOtelTraceHandler:
    def test_name(self) -> None:
        handler = OtelTraceHandler()
        assert handler.name == "otel"

    @pytest.mark.asyncio
    async def test_handle_stub(self) -> None:
        """Stub handler doesn't raise."""
        handler = OtelTraceHandler()
        event = TraceEvent(
            type="stage_start",
            trace_id="t1",
        )
        await handler.handle(event)


class TestCostAggregatorHandler:
    def test_name(self) -> None:
        handler = CostAggregatorHandler()
        assert handler.name == "cost_aggregator"

    @pytest.mark.asyncio
    async def test_tracks_llm_costs(self) -> None:
        """LLM call events accumulate token costs."""
        handler = CostAggregatorHandler()

        await handler.handle(
            TraceEvent(
                type="llm_call",
                trace_id="t1",
                data={
                    "input_tokens": 100,
                    "output_tokens": 50,
                    "cost": 0.001,
                },
            )
        )
        await handler.handle(
            TraceEvent(
                type="llm_call",
                trace_id="t1",
                data={
                    "input_tokens": 200,
                    "output_tokens": 100,
                    "cost": 0.002,
                },
            )
        )

        cost = handler.get_cost("t1")
        assert cost.input_tokens == 300
        assert cost.output_tokens == 150
        assert cost.total_cost == pytest.approx(0.003)
        assert cost.call_count == 2

    @pytest.mark.asyncio
    async def test_ignores_non_llm_events(self) -> None:
        """Non-llm_call events are ignored."""
        handler = CostAggregatorHandler()

        await handler.handle(
            TraceEvent(
                type="pipeline_start", trace_id="t1"
            )
        )
        cost = handler.get_cost("t1")
        assert cost == TraceCost()

    @pytest.mark.asyncio
    async def test_separate_traces(self) -> None:
        """Different trace IDs track separately."""
        handler = CostAggregatorHandler()

        await handler.handle(
            TraceEvent(
                type="llm_call",
                trace_id="t1",
                data={
                    "input_tokens": 100,
                    "output_tokens": 50,
                    "cost": 0.001,
                },
            )
        )
        await handler.handle(
            TraceEvent(
                type="llm_call",
                trace_id="t2",
                data={
                    "input_tokens": 500,
                    "output_tokens": 250,
                    "cost": 0.005,
                },
            )
        )

        all_costs = handler.all_costs()
        assert len(all_costs) == 2
        assert all_costs["t1"].input_tokens == 100
        assert all_costs["t2"].input_tokens == 500

    def test_get_cost_unknown_trace(self) -> None:
        """Unknown trace returns empty TraceCost."""
        handler = CostAggregatorHandler()
        cost = handler.get_cost("unknown")
        assert cost.input_tokens == 0
        assert cost.call_count == 0
