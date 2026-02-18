"""Console trace handler -- key=value log output."""

from __future__ import annotations

import logging

from artifactor.observability.events import TraceEvent

logger = logging.getLogger(__name__)


class ConsoleTraceHandler:
    """Logs trace events as key=value messages."""

    @property
    def name(self) -> str:
        return "console"

    async def handle(self, event: TraceEvent) -> None:
        parts = [
            f"trace_type={event.type}",
            f"trace_id={event.trace_id}",
            f"category={event.category}",
        ]
        for k, v in event.data.items():
            parts.append(f"{k}={v}")
        logger.info(" ".join(parts))
