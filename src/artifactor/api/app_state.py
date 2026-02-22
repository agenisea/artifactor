"""Typed application state — replaces untyped getattr() access."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from artifactor.api.event_bus import AnalysisEventBus
from artifactor.config import Settings
from artifactor.observability.dispatcher import TraceDispatcher
from artifactor.resilience.idempotency import IdempotencyGuard


@dataclass
class AppState:
    """Typed container for app.state attributes."""

    settings: Settings
    session_factory: async_sessionmaker[AsyncSession]
    event_bus: AnalysisEventBus
    idempotency: IdempotencyGuard
    dispatcher: TraceDispatcher
    analysis_tasks: dict[str, asyncio.Task[object]] = field(
        default_factory=lambda: dict[str, asyncio.Task[object]]()
    )
    analysis_queues: dict[str, asyncio.Queue[dict[str, str]]] = field(
        default_factory=lambda: dict[str, asyncio.Queue[dict[str, str]]]()
    )
    background_tasks: set[asyncio.Task[None]] = field(
        default_factory=lambda: set[asyncio.Task[None]]()
    )
