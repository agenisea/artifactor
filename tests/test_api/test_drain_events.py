"""Tests for _drain_events helper."""

from __future__ import annotations

import asyncio

import pytest

from artifactor.api.routes.projects import _drain_events
from artifactor.services.analysis_service import (
    AnalysisResult,
)


@pytest.mark.asyncio
async def test_drain_events_until_done() -> None:
    """Yields events from queue, stops when task completes."""
    queue: asyncio.Queue[dict[str, str]] = asyncio.Queue()
    queue.put_nowait({"event": "stage", "data": "e1"})
    queue.put_nowait({"event": "stage", "data": "e2"})

    # Create a task that completes immediately
    async def _noop() -> AnalysisResult:
        return AnalysisResult(project_id="p1")

    task = asyncio.create_task(_noop())
    await asyncio.sleep(0.01)  # let task complete

    events: list[dict[str, str]] = []
    async for event in _drain_events(queue, task):
        events.append(event)

    assert len(events) == 2
    assert events[0]["data"] == "e1"
    assert events[1]["data"] == "e2"
