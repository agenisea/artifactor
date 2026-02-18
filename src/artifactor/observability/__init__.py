"""Observability layer -- event dispatcher + pluggable handlers."""

from __future__ import annotations

import logging

from artifactor.config import Settings
from artifactor.observability.dispatcher import TraceDispatcher
from artifactor.observability.events import (
    TraceCategory,
    TraceEvent,
    TraceEventType,
)
from artifactor.observability.handlers.console import (
    ConsoleTraceHandler,
)

logger = logging.getLogger(__name__)

__all__ = [
    "TraceCategory",
    "TraceDispatcher",
    "TraceEvent",
    "TraceEventType",
    "initialize_tracing",
]


def initialize_tracing(settings: Settings) -> TraceDispatcher:
    """Create dispatcher and register handlers based on settings."""
    dispatcher = TraceDispatcher()

    if not settings.trace_enabled:
        return dispatcher

    dispatcher.register(ConsoleTraceHandler())

    if settings.langsmith_api_key:
        try:
            from artifactor.observability.handlers.langsmith import (
                LangSmithTraceHandler,
            )

            dispatcher.register(
                LangSmithTraceHandler(
                    api_key=settings.langsmith_api_key,
                    project=settings.langsmith_project,
                )
            )
        except ImportError:
            logger.warning(
                "event=langsmith_unavailable "
                "action=install pip install artifactor[langsmith]"
            )

    if settings.otel_enabled:
        from artifactor.observability.handlers.otel import (
            OtelTraceHandler,
        )

        dispatcher.register(OtelTraceHandler())

    return dispatcher
