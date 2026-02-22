"""Shared event types for pipeline progress reporting.

Extracted from analysis_service.py to break the circular dependency
that forced analyzer.py to use deferred TYPE_CHECKING imports.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from artifactor.constants import STAGE_LABELS, StageProgress


@dataclass(frozen=True)
class StageEvent:
    """Typed event emitted during pipeline progress."""

    name: str
    status: StageProgress
    message: str = ""
    duration_ms: float = 0.0
    # Progress fields (present during LLM chunk processing)
    completed: int | None = None
    total: int | None = None
    percent: float | None = None

    @property
    def label(self) -> str:
        """User-friendly display label from STAGE_LABELS."""
        return STAGE_LABELS[self.name]


type ProgressCallback = Callable[[StageEvent], None]
