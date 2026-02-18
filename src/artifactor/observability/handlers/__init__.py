"""Pluggable trace handler backends."""

from __future__ import annotations

from typing import Protocol

from artifactor.observability.events import TraceEvent


class TraceHandler(Protocol):
    """Pluggable trace handler -- implement for each backend."""

    @property
    def name(self) -> str: ...

    async def handle(self, event: TraceEvent) -> None: ...
