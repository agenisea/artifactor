"""OpenTelemetry trace handler -- stub for future implementation."""

from __future__ import annotations

import logging

from artifactor.observability.events import TraceEvent

logger = logging.getLogger(__name__)


class OtelTraceHandler:
    """Maps trace events to OTEL spans. Stub -- not yet implemented."""

    @property
    def name(self) -> str:
        return "otel"

    async def handle(self, event: TraceEvent) -> None:
        """Placeholder -- logs event type at debug level."""
        logger.debug(
            "event=otel_stub trace_type=%s trace_id=%s",
            event.type,
            event.trace_id,
        )
