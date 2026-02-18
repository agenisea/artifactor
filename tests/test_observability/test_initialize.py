"""Tests for observability bootstrap."""

from __future__ import annotations

from artifactor.config import Settings
from artifactor.observability import initialize_tracing


class TestInitializeTracing:
    def test_default_registers_console(self) -> None:
        """Console handler is always registered."""
        settings = Settings(trace_enabled=True)
        dispatcher = initialize_tracing(settings)
        assert dispatcher.handler_count == 1

    def test_trace_disabled_returns_empty(self) -> None:
        """Disabled tracing returns dispatcher with no handlers."""
        settings = Settings(trace_enabled=False)
        dispatcher = initialize_tracing(settings)
        assert dispatcher.handler_count == 0
