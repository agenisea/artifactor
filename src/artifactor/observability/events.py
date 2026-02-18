"""Typed trace events emitted during pipeline execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

TraceEventType = Literal[
    "pipeline_start",
    "pipeline_end",
    "phase_start",
    "phase_end",
    "stage_start",
    "stage_end",
    "llm_call",
    "error",
]

TraceCategory = Literal[
    "pipeline",
    "analysis",
    "llm",
    "quality",
    "generation",
]


@dataclass(frozen=True)
class TraceEvent:
    """Immutable trace event emitted during pipeline execution."""

    type: TraceEventType
    trace_id: str
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(UTC)
    )
    category: TraceCategory = "pipeline"
    data: dict[str, Any] = field(
        default_factory=lambda: dict[str, Any]()
    )
