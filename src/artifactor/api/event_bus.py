"""In-memory per-project pub/sub with replay for SSE stream joining.

When a late subscriber (e.g. a browser reconnect or a second tab) POSTs
to /analyze while analysis is already running, the backend subscribes it
to the existing event bus channel instead of rejecting.  The subscriber
receives all previously published events (replay) followed by live events,
so its SSE stream is indistinguishable from the original.

Single-process only — each worker has its own instance.
"""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field


@dataclass
class _Channel:
    """Per-project event channel with replay buffer."""

    events: deque[dict[str, str]] = field(
        default_factory=lambda: deque[dict[str, str]](),
    )
    subscribers: list[asyncio.Queue[dict[str, str] | None]] = field(
        default_factory=lambda: list[asyncio.Queue[dict[str, str] | None]](),
    )
    max_replay: int = 500


class AnalysisEventBus:
    """Per-project pub/sub with replay buffer for SSE stream joining.

    Thread-safety: all mutating operations acquire ``_lock`` (asyncio.Lock).
    ``publish`` is synchronous but only appends to lists, so it is safe
    to call from a sync callback (e.g. ``add_done_callback``).
    """

    def __init__(self, max_replay: int = 500) -> None:
        self._channels: dict[str, _Channel] = {}
        self._lock = asyncio.Lock()
        self._max_replay = max_replay

    def has_channel(self, project_id: str) -> bool:
        """Check whether a live channel exists for *project_id*."""
        return project_id in self._channels

    async def create_channel(self, project_id: str) -> None:
        """Create (or reset) a channel for *project_id*."""
        async with self._lock:
            self._channels[project_id] = _Channel(
                events=deque(maxlen=self._max_replay),
                max_replay=self._max_replay,
            )

    def publish(self, project_id: str, event: dict[str, str]) -> None:
        """Publish *event* to all current subscribers and the replay buffer.

        No-op if the channel does not exist (e.g. already completed).
        deque(maxlen=...) automatically drops the oldest event on overflow.
        """
        ch = self._channels.get(project_id)
        if ch is None:
            return
        ch.events.append(event)
        for q in ch.subscribers:
            q.put_nowait(event)

    def get_latest_events(
        self, project_id: str
    ) -> list[dict[str, str]]:
        """Return a copy of the replay buffer for read-only access."""
        ch = self._channels.get(project_id)
        if ch is None:
            return []
        return list(ch.events)

    async def subscribe(
        self,
        project_id: str,
    ) -> asyncio.Queue[dict[str, str] | None]:
        """Subscribe to *project_id* and receive replayed + live events.

        If no channel exists, returns a queue with an immediate ``None``
        sentinel so the caller can detect the race.
        """
        async with self._lock:
            ch = self._channels.get(project_id)
            if ch is None:
                q: asyncio.Queue[dict[str, str] | None] = asyncio.Queue()
                q.put_nowait(None)
                return q
            q = asyncio.Queue()
            for ev in ch.events:
                q.put_nowait(ev)
            ch.subscribers.append(q)
            return q

    async def complete(self, project_id: str) -> None:
        """Signal end-of-stream and remove the channel.

        Idempotent: no-op if the channel was already removed.
        """
        async with self._lock:
            ch = self._channels.pop(project_id, None)
        if ch is None:
            return
        for q in ch.subscribers:
            q.put_nowait(None)
