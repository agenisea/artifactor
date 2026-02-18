"""Tests for trace event types."""

from __future__ import annotations

from datetime import UTC, datetime

from artifactor.observability.events import TraceEvent


class TestTraceEvent:
    def test_defaults(self) -> None:
        """Event has sensible defaults."""
        event = TraceEvent(
            type="pipeline_start", trace_id="t1"
        )
        assert event.category == "pipeline"
        assert event.data == {}
        assert isinstance(event.timestamp, datetime)

    def test_frozen(self) -> None:
        """Events are immutable."""
        event = TraceEvent(
            type="pipeline_start", trace_id="t1"
        )
        try:
            event.trace_id = "t2"  # type: ignore[misc]
            raise AssertionError("Should not be mutable")
        except AttributeError:
            pass

    def test_custom_data(self) -> None:
        """Data dict carries arbitrary payload."""
        event = TraceEvent(
            type="llm_call",
            trace_id="t1",
            category="llm",
            data={
                "model": "claude",
                "input_tokens": 100,
            },
        )
        assert event.data["model"] == "claude"
        assert event.data["input_tokens"] == 100

    def test_timestamp_is_utc(self) -> None:
        """Timestamp uses UTC."""
        event = TraceEvent(
            type="pipeline_start", trace_id="t1"
        )
        assert event.timestamp.tzinfo == UTC
