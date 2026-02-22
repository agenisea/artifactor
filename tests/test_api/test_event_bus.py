"""Tests for AnalysisEventBus."""

from __future__ import annotations

import asyncio

import pytest

from artifactor.api.event_bus import AnalysisEventBus


@pytest.mark.asyncio
async def test_publish_subscribe() -> None:
    """Basic: publish then receive via subscriber."""
    bus = AnalysisEventBus()
    await bus.create_channel("proj-1")

    queue = await bus.subscribe("proj-1")
    bus.publish("proj-1", {"event": "stage", "data": "a"})
    await bus.complete("proj-1")

    events: list[dict[str, str]] = []
    while True:
        ev = await queue.get()
        if ev is None:
            break
        events.append(ev)

    assert len(events) == 1
    assert events[0]["data"] == "a"


@pytest.mark.asyncio
async def test_replay_on_late_subscribe() -> None:
    """Late subscriber receives replayed events."""
    bus = AnalysisEventBus()
    await bus.create_channel("proj-1")

    bus.publish("proj-1", {"event": "stage", "data": "1"})
    bus.publish("proj-1", {"event": "stage", "data": "2"})

    # Subscribe after 2 events published
    queue = await bus.subscribe("proj-1")
    bus.publish("proj-1", {"event": "stage", "data": "3"})
    await bus.complete("proj-1")

    events: list[dict[str, str]] = []
    while True:
        ev = await queue.get()
        if ev is None:
            break
        events.append(ev)

    assert len(events) == 3
    assert [e["data"] for e in events] == ["1", "2", "3"]


@pytest.mark.asyncio
async def test_subscribe_no_channel() -> None:
    """subscribe() with no channel returns immediate sentinel."""
    bus = AnalysisEventBus()
    queue = await bus.subscribe("nonexistent")

    ev = await queue.get()
    assert ev is None


@pytest.mark.asyncio
async def test_has_channel() -> None:
    """has_channel reflects lifecycle."""
    bus = AnalysisEventBus()
    assert bus.has_channel("proj-1") is False

    await bus.create_channel("proj-1")
    assert bus.has_channel("proj-1") is True

    await bus.complete("proj-1")
    assert bus.has_channel("proj-1") is False


@pytest.mark.asyncio
async def test_multiple_subscribers() -> None:
    """Fan-out: all subscribers receive same events."""
    bus = AnalysisEventBus()
    await bus.create_channel("proj-1")

    q1 = await bus.subscribe("proj-1")
    q2 = await bus.subscribe("proj-1")

    bus.publish("proj-1", {"event": "stage", "data": "x"})
    await bus.complete("proj-1")

    results = []
    for q in [q1, q2]:
        events: list[dict[str, str]] = []
        while True:
            ev = await q.get()
            if ev is None:
                break
            events.append(ev)
        results.append(events)

    assert len(results[0]) == 1
    assert len(results[1]) == 1
    assert results[0][0]["data"] == "x"
    assert results[1][0]["data"] == "x"


@pytest.mark.asyncio
async def test_complete_removes_channel() -> None:
    """complete() removes channel; publish is no-op after."""
    bus = AnalysisEventBus()
    await bus.create_channel("proj-1")

    await bus.complete("proj-1")
    assert bus.has_channel("proj-1") is False

    # Publish after complete is silent no-op
    bus.publish("proj-1", {"event": "stage", "data": "late"})


@pytest.mark.asyncio
async def test_double_complete_idempotent() -> None:
    """Second complete() is a no-op."""
    bus = AnalysisEventBus()
    await bus.create_channel("proj-1")
    q = await bus.subscribe("proj-1")

    await bus.complete("proj-1")
    await bus.complete("proj-1")  # Should not raise

    ev = await q.get()
    assert ev is None


@pytest.mark.asyncio
async def test_replay_capped_at_max() -> None:
    """Replay buffer drops oldest events when exceeding max_replay."""
    bus = AnalysisEventBus(max_replay=3)
    await bus.create_channel("proj-1")

    for i in range(5):
        bus.publish(
            "proj-1", {"event": "stage", "data": str(i)}
        )

    # Late subscriber should see only last 3
    queue = await bus.subscribe("proj-1")
    await bus.complete("proj-1")

    events: list[dict[str, str]] = []
    while True:
        ev = await queue.get()
        if ev is None:
            break
        events.append(ev)

    assert len(events) == 3
    assert [e["data"] for e in events] == ["2", "3", "4"]


@pytest.mark.asyncio
async def test_get_latest_events() -> None:
    """get_latest_events returns a copy of the replay buffer."""
    bus = AnalysisEventBus()
    await bus.create_channel("proj-1")

    bus.publish("proj-1", {"event": "stage", "data": "a"})
    bus.publish("proj-1", {"event": "stage", "data": "b"})

    events = bus.get_latest_events("proj-1")
    assert len(events) == 2
    assert events[0]["data"] == "a"
    assert events[1]["data"] == "b"

    # Verify it's a copy (mutating returned list doesn't affect bus)
    events.clear()
    assert len(bus.get_latest_events("proj-1")) == 2


@pytest.mark.asyncio
async def test_get_latest_events_no_channel() -> None:
    """get_latest_events returns empty list for non-existent channel."""
    bus = AnalysisEventBus()
    assert bus.get_latest_events("nonexistent") == []


@pytest.mark.asyncio
async def test_deque_eviction() -> None:
    """deque(maxlen=...) automatically drops oldest events."""
    bus = AnalysisEventBus(max_replay=3)
    await bus.create_channel("proj-1")

    for i in range(5):
        bus.publish(
            "proj-1", {"event": "stage", "data": str(i)}
        )

    events = bus.get_latest_events("proj-1")
    assert len(events) == 3
    assert [e["data"] for e in events] == ["2", "3", "4"]


@pytest.mark.asyncio
async def test_concurrent_subscribe_and_complete() -> None:
    """Concurrent subscribe + complete does not deadlock."""
    bus = AnalysisEventBus()
    await bus.create_channel("proj-1")
    bus.publish("proj-1", {"event": "stage", "data": "a"})

    async def _subscribe_drain() -> int:
        q = await bus.subscribe("proj-1")
        count = 0
        while True:
            ev = await asyncio.wait_for(q.get(), timeout=2.0)
            if ev is None:
                break
            count += 1
        return count

    count, _ = await asyncio.gather(
        _subscribe_drain(),
        bus.complete("proj-1"),
    )
    assert count >= 1
