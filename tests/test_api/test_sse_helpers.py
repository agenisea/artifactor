"""Tests for SSE event builder functions."""

from __future__ import annotations

import json

from artifactor.api.routes.projects import (
    _complete_event,
    _error_event,
    _paused_event,
    _stage_event,
)
from artifactor.constants import SSEEvent, StageProgress
from artifactor.services.analysis_service import (
    AnalysisResult,
    StageStatus,
)
from artifactor.services.events import StageEvent as SE


class TestErrorEvent:
    def test_error_event_format(self) -> None:
        result = _error_event("Something broke")
        assert result["event"] == SSEEvent.ERROR
        data = json.loads(result["data"])
        assert data["error"] == "Something broke"


class TestStageEvent:
    def test_stage_event_format(self) -> None:
        event = SE(
            name="ingestion_resolve",
            status=StageProgress.RUNNING,
            message="Resolving...",
        )
        result = _stage_event(event)
        assert result["event"] == SSEEvent.STAGE
        data = json.loads(result["data"])
        assert data["name"] == "ingestion_resolve"
        assert data["status"] == StageProgress.RUNNING
        assert data["message"] == "Resolving..."
        assert "completed" not in data

    def test_stage_event_with_progress(self) -> None:
        event = SE(
            name="llm_analysis",
            status=StageProgress.RUNNING,
            message="Analyzing...",
            completed=5,
            total=10,
            percent=50.0,
        )
        result = _stage_event(event)
        data = json.loads(result["data"])
        assert data["completed"] == 5
        assert data["total"] == 10
        assert data["percent"] == 50.0


class TestCompleteEvent:
    def test_complete_event_format(self) -> None:
        result_obj = AnalysisResult(
            project_id="proj-1",
            stages=[
                StageStatus(
                    name="s1", ok=True, duration_ms=10.0
                ),
                StageStatus(
                    name="s2",
                    ok=False,
                    duration_ms=5.0,
                    error="fail",
                ),
            ],
            total_duration_ms=100.0,
        )
        event = _complete_event("proj-1", result_obj)
        assert event["event"] == SSEEvent.COMPLETE
        data = json.loads(event["data"])
        assert data["project_id"] == "proj-1"
        assert data["sections"] == 0
        assert data["stages_ok"] == 1
        assert data["stages_failed"] == 1
        assert data["partial"] is True
        assert data["duration_ms"] == 100.0


class TestPausedEvent:
    def test_paused_event_format(self) -> None:
        result = _paused_event()
        assert result["event"] == SSEEvent.PAUSED
        data = json.loads(result["data"])
        assert data["message"] == "Analysis paused"
