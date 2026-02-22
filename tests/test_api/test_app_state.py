"""Tests for typed AppState access."""

from __future__ import annotations

from unittest.mock import MagicMock

from artifactor.api.app_state import AppState
from artifactor.api.event_bus import AnalysisEventBus
from artifactor.config import Settings
from artifactor.observability.dispatcher import TraceDispatcher
from artifactor.resilience.idempotency import IdempotencyGuard


class TestAppState:
    def test_typed_app_state_access(self) -> None:
        """AppState provides typed access to all fields."""
        settings = Settings()
        session_factory = MagicMock()
        event_bus = AnalysisEventBus()
        idempotency = IdempotencyGuard()
        dispatcher = TraceDispatcher()

        state = AppState(
            settings=settings,
            session_factory=session_factory,
            event_bus=event_bus,
            idempotency=idempotency,
            dispatcher=dispatcher,
        )

        assert state.settings is settings
        assert state.session_factory is session_factory
        assert state.event_bus is event_bus
        assert state.idempotency is idempotency
        assert state.dispatcher is dispatcher
        assert isinstance(state.analysis_tasks, dict)
        assert isinstance(state.analysis_queues, dict)
        assert isinstance(state.background_tasks, set)
