"""Tests for late-joiner stream helper."""

from __future__ import annotations

import asyncio

import pytest

from artifactor.api.event_bus import AnalysisEventBus
from artifactor.api.routes.projects import (
    _late_joiner_stream,
)


@pytest.mark.asyncio
async def test_late_joiner_stream_replays() -> None:
    """Late-joiner receives replayed + live events, stops at None."""
    bus = AnalysisEventBus()
    project_id = "proj-1"

    # Create channel and publish some events
    await bus.create_channel(project_id)
    bus.publish(
        project_id,
        {"event": "stage", "data": "event1"},
    )
    bus.publish(
        project_id,
        {"event": "stage", "data": "event2"},
    )

    # Schedule channel completion after a short delay
    async def _complete_later() -> None:
        await asyncio.sleep(0.05)
        await bus.complete(project_id)

    asyncio.create_task(_complete_later())

    # Collect all events from the late-joiner stream
    events: list[dict[str, str]] = []
    async for event in _late_joiner_stream(
        bus, project_id
    ):
        events.append(event)

    # Should have received the 2 replayed events
    assert len(events) == 2
    assert events[0]["data"] == "event1"
    assert events[1]["data"] == "event2"
