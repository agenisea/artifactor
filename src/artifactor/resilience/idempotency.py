"""In-flight request deduplication.

IdempotencyGuard prevents duplicate concurrent operations for the same key.
If operation A is running for key "analyze:proj1" and operation B arrives
for the same key, B awaits A's result instead of running a duplicate.

Single-process only — each Gunicorn worker has its own instance.
For MVP with SQLite (single writer), this is sufficient.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class _InFlight:
    key: str
    event: asyncio.Event = field(default_factory=asyncio.Event)
    result: Any = None
    error: BaseException | None = None


class IdempotencyGuard:
    """Deduplicates in-flight async operations by key.

    Usage::

        guard = IdempotencyGuard()
        result = await guard.execute("analyze:proj1", my_async_fn)
    """

    def __init__(self) -> None:
        self._in_flight: dict[str, _InFlight] = {}
        self._lock = asyncio.Lock()

    async def execute(
        self,
        key: str,
        operation: Callable[[], Awaitable[Any]],
    ) -> Any:
        """Run operation, deduplicating by key.

        If an operation with the same key is already running,
        await its result instead of running a duplicate.

        Uses asyncio.Lock to prevent races between event.set()
        and _in_flight.pop() that could allow a third caller
        to start a duplicate operation.
        """
        tracker: _InFlight | None = None
        async with self._lock:
            existing = self._in_flight.get(key)
            if existing is None:
                tracker = _InFlight(key=key)
                self._in_flight[key] = tracker

        # Waiting case: lock released, await result
        if existing is not None:
            await existing.event.wait()
            if existing.error:
                raise existing.error
            return existing.result

        # Owner case: tracker is guaranteed set (existing was None)
        if tracker is None:
            raise RuntimeError("unreachable: tracker unset")
        try:
            result = await operation()
            tracker.result = result
            return result
        except BaseException as exc:
            tracker.error = exc
            raise
        finally:
            tracker.event.set()
            async with self._lock:
                self._in_flight.pop(key, None)

    @property
    def active_keys(self) -> list[str]:
        """Return currently in-flight operation keys."""
        return list(self._in_flight.keys())
