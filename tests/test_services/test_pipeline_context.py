"""Tests for PipelineContext report methods."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from artifactor.config import Settings
from artifactor.constants import StageProgress
from artifactor.services.analysis_service import (
    PipelineContext,
    StageStatus,
)
from artifactor.services.events import StageEvent


class TestContextReport:
    def test_report_calls_on_progress(self) -> None:
        """ctx.report() calls on_progress callback."""
        callback = MagicMock()
        ctx = PipelineContext(
            project_id="p1",
            repo_path=Path("/tmp"),
            settings=Settings(),
            on_progress=callback,
        )
        event = StageEvent(
            name="test_stage",
            status=StageProgress.RUNNING,
        )
        ctx.report(event)
        callback.assert_called_once_with(event)

    def test_report_noop_without_callback(self) -> None:
        """ctx.report() is no-op when on_progress is None."""
        ctx = PipelineContext(
            project_id="p1",
            repo_path=Path("/tmp"),
            settings=Settings(),
        )
        # Should not raise
        ctx.report(
            StageEvent(
                name="test_stage",
                status=StageProgress.RUNNING,
            )
        )

    def test_report_done_emits_correct_status(self) -> None:
        """ctx.report_done() emits DONE for ok=True."""
        events: list[StageEvent] = []
        ctx = PipelineContext(
            project_id="p1",
            repo_path=Path("/tmp"),
            settings=Settings(),
            on_progress=lambda e: events.append(e),
        )
        status = StageStatus(
            name="quality", ok=True, duration_ms=42.0
        )
        ctx.report_done(status)
        assert len(events) == 1
        assert events[0].name == "quality"
        assert events[0].status == StageProgress.DONE
        assert events[0].duration_ms == 42.0

    def test_report_done_emits_error_status(self) -> None:
        """ctx.report_done() emits ERROR for ok=False."""
        events: list[StageEvent] = []
        ctx = PipelineContext(
            project_id="p1",
            repo_path=Path("/tmp"),
            settings=Settings(),
            on_progress=lambda e: events.append(e),
        )
        status = StageStatus(
            name="quality",
            ok=False,
            duration_ms=10.0,
            error="validation failed",
        )
        ctx.report_done(status)
        assert len(events) == 1
        assert events[0].status == StageProgress.ERROR
        assert events[0].message == "validation failed"
