"""Fan-out dispatcher for trace events."""

from __future__ import annotations

import logging

from artifactor.observability.events import TraceEvent
from artifactor.observability.handlers import TraceHandler

logger = logging.getLogger(__name__)


class TraceDispatcher:
    """Fan-out dispatcher -- emits events to all registered handlers.

    Best-effort delivery: handler errors are logged, never raised.
    """

    def __init__(self) -> None:
        self._handlers: list[TraceHandler] = []

    def register(self, handler: TraceHandler) -> None:
        """Register a handler. Duplicates (by name) are ignored."""
        if not any(h.name == handler.name for h in self._handlers):
            self._handlers.append(handler)

    async def emit(self, event: TraceEvent) -> None:
        """Best-effort fan-out to all registered handlers."""
        for handler in self._handlers:
            try:
                await handler.handle(event)
            except Exception:
                logger.warning(
                    "event=trace_handler_error handler=%s",
                    handler.name,
                )

    @property
    def handler_count(self) -> int:
        return len(self._handlers)
