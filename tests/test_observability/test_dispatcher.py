"""Tests for the trace event dispatcher."""

from __future__ import annotations

import pytest

from artifactor.observability.dispatcher import TraceDispatcher
from artifactor.observability.events import TraceEvent


class TestTraceDispatcher:
    @pytest.mark.asyncio
    async def test_emit_fans_out_to_handlers(self) -> None:
        """Event is delivered to all registered handlers."""
        received: list[TraceEvent] = []

        class Collector:
            @property
            def name(self) -> str:
                return "collector"

            async def handle(self, event: TraceEvent) -> None:
                received.append(event)

        dispatcher = TraceDispatcher()
        dispatcher.register(Collector())

        event = TraceEvent(
            type="pipeline_start", trace_id="t1"
        )
        await dispatcher.emit(event)

        assert len(received) == 1
        assert received[0].trace_id == "t1"

    @pytest.mark.asyncio
    async def test_duplicate_handler_ignored(self) -> None:
        """Registering the same handler name twice is a no-op."""

        class Stub:
            @property
            def name(self) -> str:
                return "stub"

            async def handle(self, event: TraceEvent) -> None:
                pass

        dispatcher = TraceDispatcher()
        dispatcher.register(Stub())
        dispatcher.register(Stub())

        assert dispatcher.handler_count == 1

    @pytest.mark.asyncio
    async def test_handler_error_does_not_propagate(
        self,
    ) -> None:
        """A failing handler does not crash the dispatcher."""

        class BadHandler:
            @property
            def name(self) -> str:
                return "bad"

            async def handle(self, event: TraceEvent) -> None:
                msg = "boom"
                raise RuntimeError(msg)

        dispatcher = TraceDispatcher()
        dispatcher.register(BadHandler())

        event = TraceEvent(
            type="pipeline_start", trace_id="t1"
        )
        await dispatcher.emit(event)  # should not raise

    @pytest.mark.asyncio
    async def test_emit_with_no_handlers(self) -> None:
        """Emitting with no handlers is a no-op."""
        dispatcher = TraceDispatcher()
        event = TraceEvent(
            type="pipeline_end", trace_id="t1"
        )
        await dispatcher.emit(event)  # should not raise

    @pytest.mark.asyncio
    async def test_multiple_handlers(self) -> None:
        """Multiple distinct handlers all receive events."""
        counts: dict[str, int] = {}

        def make_handler(handler_name: str):  # noqa: ANN202
            class H:
                @property
                def name(self) -> str:
                    return handler_name

                async def handle(
                    self, event: TraceEvent
                ) -> None:
                    counts[handler_name] = (
                        counts.get(handler_name, 0) + 1
                    )

            return H()

        dispatcher = TraceDispatcher()
        dispatcher.register(make_handler("a"))
        dispatcher.register(make_handler("b"))
        dispatcher.register(make_handler("c"))

        event = TraceEvent(
            type="pipeline_start", trace_id="t1"
        )
        await dispatcher.emit(event)

        assert counts == {"a": 1, "b": 1, "c": 1}
