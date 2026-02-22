"""Tests for _on_analysis_done callback."""

from __future__ import annotations

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from artifactor.api.routes.projects import (
    _on_analysis_done,
)
from artifactor.constants import ProjectStatus
from artifactor.services.analysis_service import (
    AnalysisResult,
)


def _make_completed_task(
    result: AnalysisResult | None = None,
) -> asyncio.Task[AnalysisResult]:
    """Create a task that has already completed with a result."""
    fut: asyncio.Future[AnalysisResult] = asyncio.Future()
    fut.set_result(
        result or AnalysisResult(project_id="p1")
    )
    # Wrap in a task-like object
    task = MagicMock(spec=asyncio.Task)
    task.cancelled.return_value = False
    task.exception.return_value = None
    task.done.return_value = True
    return task


def _make_failed_task(
    exc: Exception,
) -> asyncio.Task[AnalysisResult]:
    """Create a task that failed with an exception."""
    task = MagicMock(spec=asyncio.Task)
    task.cancelled.return_value = False
    task.exception.return_value = exc
    task.done.return_value = True
    return task


def _make_cancelled_task() -> asyncio.Task[AnalysisResult]:
    """Create a task that was cancelled."""
    task = MagicMock(spec=asyncio.Task)
    task.cancelled.return_value = True
    task.done.return_value = True
    return task


@pytest.mark.asyncio
async def test_on_analysis_done_success() -> None:
    """Task success -> CAS(ANALYZED) + event_bus.complete()."""
    task = _make_completed_task()
    tasks_dict: dict[str, asyncio.Task[object]] = {
        "p1": task
    }
    service = AsyncMock()
    service.try_set_status_immediate.return_value = True
    event_bus = AsyncMock()
    bg_tasks: set[asyncio.Task[None]] = set()

    _on_analysis_done(
        task,
        project_id="p1",
        analysis_tasks=tasks_dict,
        service=service,
        event_bus=event_bus,
        bg_tasks=bg_tasks,
    )

    # Let the background task run
    await asyncio.sleep(0.05)

    service.try_set_status_immediate.assert_awaited_once_with(
        "p1",
        {ProjectStatus.ANALYZING},
        ProjectStatus.ANALYZED,
    )
    event_bus.complete.assert_awaited_once_with("p1")
    assert "p1" not in tasks_dict


@pytest.mark.asyncio
async def test_on_analysis_done_failure(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Task exception -> CAS(ERROR) + logs exception."""
    exc = RuntimeError("LLM timeout")
    task = _make_failed_task(exc)
    tasks_dict: dict[str, asyncio.Task[object]] = {
        "p1": task
    }
    service = AsyncMock()
    service.try_set_status_immediate.return_value = True
    event_bus = AsyncMock()
    bg_tasks: set[asyncio.Task[None]] = set()

    with caplog.at_level(logging.ERROR):
        _on_analysis_done(
            task,
            project_id="p1",
            analysis_tasks=tasks_dict,
            service=service,
            event_bus=event_bus,
            bg_tasks=bg_tasks,
        )

    assert "analysis_exception" in caplog.text
    assert "p1" in caplog.text

    await asyncio.sleep(0.05)

    service.try_set_status_immediate.assert_awaited_once_with(
        "p1",
        {ProjectStatus.ANALYZING},
        ProjectStatus.ERROR,
    )
    event_bus.complete.assert_awaited_once_with("p1")


@pytest.mark.asyncio
async def test_on_analysis_done_cancelled(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Task cancelled -> CAS(ERROR) + logs warning."""
    task = _make_cancelled_task()
    tasks_dict: dict[str, asyncio.Task[object]] = {
        "p1": task
    }
    service = AsyncMock()
    service.try_set_status_immediate.return_value = True
    event_bus = AsyncMock()
    bg_tasks: set[asyncio.Task[None]] = set()

    with caplog.at_level(logging.WARNING):
        _on_analysis_done(
            task,
            project_id="p1",
            analysis_tasks=tasks_dict,
            service=service,
            event_bus=event_bus,
            bg_tasks=bg_tasks,
        )

    assert "analysis_cancelled" in caplog.text

    await asyncio.sleep(0.05)

    service.try_set_status_immediate.assert_awaited_once_with(
        "p1",
        {ProjectStatus.ANALYZING},
        ProjectStatus.ERROR,
    )


@pytest.mark.asyncio
async def test_on_analysis_done_logs_exception_even_without_service(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Exception is logged even when service=None."""
    exc = RuntimeError("crash")
    task = _make_failed_task(exc)
    tasks_dict: dict[str, asyncio.Task[object]] = {}
    event_bus = AsyncMock()
    bg_tasks: set[asyncio.Task[None]] = set()

    with caplog.at_level(logging.ERROR):
        _on_analysis_done(
            task,
            project_id="p1",
            analysis_tasks=tasks_dict,
            service=None,
            event_bus=event_bus,
            bg_tasks=bg_tasks,
        )

    assert "analysis_exception" in caplog.text
    assert "p1" in caplog.text

    await asyncio.sleep(0.05)

    event_bus.complete.assert_awaited_once_with("p1")
