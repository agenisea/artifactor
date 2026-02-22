"""Tests for _create_and_register_task helper."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from artifactor.api.app_state import AppState
from artifactor.api.event_bus import AnalysisEventBus
from artifactor.api.routes.projects import (
    _create_and_register_task,
)
from artifactor.config import Settings
from artifactor.observability.dispatcher import TraceDispatcher
from artifactor.resilience.idempotency import IdempotencyGuard
from artifactor.services.analysis_service import (
    AnalysisResult,
)


@pytest.mark.asyncio
async def test_create_and_register_task() -> None:
    """Task is created and registered in analysis_tasks."""
    event_bus = AnalysisEventBus()
    state = AppState(
        settings=Settings(),
        session_factory=None,  # pyright: ignore[reportArgumentType]
        event_bus=event_bus,
        idempotency=IdempotencyGuard(),
        dispatcher=TraceDispatcher(),
    )

    fake_result = AnalysisResult(project_id="p1")
    with patch(
        "artifactor.api.routes.projects.run_analysis",
        new_callable=AsyncMock,
        return_value=fake_result,
    ):
        task = await _create_and_register_task(
            state,
            "p1",
            "/tmp/repo",
            "main",
            lambda _: None,
        )

    assert "p1" in state.analysis_tasks
    assert state.analysis_tasks["p1"] is task

    # Wait for task to complete
    result = await task
    assert result.project_id == "p1"


@pytest.mark.asyncio
async def test_create_task_wraps_with_idempotency() -> None:
    """Task coroutine is wrapped via state.idempotency.execute."""
    idempotency = IdempotencyGuard()
    event_bus = AnalysisEventBus()
    state = AppState(
        settings=Settings(),
        session_factory=None,  # pyright: ignore[reportArgumentType]
        event_bus=event_bus,
        idempotency=idempotency,
        dispatcher=TraceDispatcher(),
    )

    call_count = 0

    async def _fake_run(**kwargs: object) -> AnalysisResult:
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.5)
        return AnalysisResult(project_id="p1")

    with patch(
        "artifactor.api.routes.projects.run_analysis",
        side_effect=_fake_run,
    ):
        # Launch two concurrent calls — idempotency should deduplicate
        task1 = await _create_and_register_task(
            state, "p1", "/tmp/repo", "main", lambda _: None
        )
        task2 = await _create_and_register_task(
            state, "p1", "/tmp/repo", "main", lambda _: None
        )
        await asyncio.gather(task1, task2)

    # IdempotencyGuard keys on "analyze:p1" — second call
    # waits for first, so run_analysis is called only once.
    assert call_count == 1
