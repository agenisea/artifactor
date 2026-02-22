"""Tests for enriched /status endpoint and _derive_stages helper."""

from __future__ import annotations

import json

from artifactor.api.routes.projects import _derive_stages
from artifactor.constants import SSEEvent


class TestDeriveStages:
    def test_derive_stages_extracts_latest(self) -> None:
        """Keeps only the latest event per stage name."""
        events = [
            {
                "event": SSEEvent.STAGE,
                "data": json.dumps(
                    {
                        "name": "ingestion_resolve",
                        "label": "Resolving",
                        "status": "running",
                        "message": "Starting...",
                        "duration_ms": 0.0,
                    }
                ),
            },
            {
                "event": SSEEvent.STAGE,
                "data": json.dumps(
                    {
                        "name": "ingestion_resolve",
                        "label": "Resolving",
                        "status": "done",
                        "message": "Done",
                        "duration_ms": 123.4,
                    }
                ),
            },
            {
                "event": SSEEvent.STAGE,
                "data": json.dumps(
                    {
                        "name": "static_analysis",
                        "label": "Static",
                        "status": "running",
                        "message": "Analyzing...",
                        "duration_ms": 0.0,
                    }
                ),
            },
        ]
        stages = _derive_stages(events)
        assert len(stages) == 2
        assert stages[0]["name"] == "ingestion_resolve"
        assert stages[0]["status"] == "done"
        assert stages[0]["duration_ms"] == 123.4
        assert stages[1]["name"] == "static_analysis"

    def test_derive_stages_filters_non_stage_events(self) -> None:
        """Non-stage events are ignored."""
        events = [
            {
                "event": SSEEvent.COMPLETE,
                "data": json.dumps({"project_id": "abc"}),
            },
            {
                "event": SSEEvent.ERROR,
                "data": json.dumps({"error": "fail"}),
            },
        ]
        stages = _derive_stages(events)
        assert stages == []

    def test_derive_stages_with_progress_fields(self) -> None:
        """Progress fields (completed, total, percent) are preserved."""
        events = [
            {
                "event": SSEEvent.STAGE,
                "data": json.dumps(
                    {
                        "name": "llm_analysis",
                        "label": "LLM",
                        "status": "running",
                        "message": "5/10",
                        "duration_ms": 0.0,
                        "completed": 5,
                        "total": 10,
                        "percent": 50.0,
                    }
                ),
            },
        ]
        stages = _derive_stages(events)
        assert len(stages) == 1
        assert stages[0]["completed"] == 5
        assert stages[0]["total"] == 10
        assert stages[0]["percent"] == 50.0

    def test_derive_stages_empty(self) -> None:
        """Empty event list returns empty stages."""
        assert _derive_stages([]) == []

    def test_derive_stages_bad_json_skipped(self) -> None:
        """Malformed JSON data is skipped, not raised."""
        events = [
            {"event": SSEEvent.STAGE, "data": "not-json"},
            {
                "event": SSEEvent.STAGE,
                "data": json.dumps(
                    {
                        "name": "ok",
                        "label": "OK",
                        "status": "done",
                        "message": "",
                        "duration_ms": 1.0,
                    }
                ),
            },
        ]
        stages = _derive_stages(events)
        assert len(stages) == 1
        assert stages[0]["name"] == "ok"
