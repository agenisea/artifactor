"""Tests for analysis SSE endpoint."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from artifactor.constants import (
    ProjectStatus,
    SSEEvent,
    StageProgress,
)
from artifactor.main import app
from artifactor.outputs.base import SectionOutput
from artifactor.services.analysis_service import (
    AnalysisResult,
    StageStatus,
)
from artifactor.services.events import StageEvent
from tests.conftest import (
    parse_sse_events as _parse_sse_events,
)
from tests.conftest import (
    setup_test_app,
)


def _fake_analysis_result(project_id: str) -> AnalysisResult:
    """Build a minimal AnalysisResult for testing."""
    return AnalysisResult(
        project_id=project_id,
        stages=[
            StageStatus(
                name="ingestion_resolve", ok=True, duration_ms=10.0
            ),
            StageStatus(
                name="static_analysis", ok=True, duration_ms=20.0
            ),
        ],
        sections=[
            SectionOutput(
                title="Overview",
                section_name="executive_overview",
                content="# Overview\n\nTest.",
                confidence=0.9,
            )
        ],
        total_duration_ms=100.0,
    )


async def _mock_run_analysis(
    repo_path, settings=None, sections=None,
    branch="main", on_progress=None, dispatcher=None,
    session_factory=None, project_id=None,
):
    """Mock run_analysis that emits stage events without LLM calls."""
    if on_progress:
        on_progress(StageEvent(
            name="ingestion_resolve",
            status=StageProgress.RUNNING,
            message="Resolving...",
        ))
        on_progress(StageEvent(
            name="ingestion_resolve",
            status=StageProgress.DONE,
            duration_ms=10.0,
        ))
        on_progress(StageEvent(
            name="static_analysis",
            status=StageProgress.RUNNING,
            message="Analyzing...",
        ))
        on_progress(StageEvent(
            name="static_analysis",
            status=StageProgress.DONE,
            duration_ms=20.0,
        ))
    # project_id is generated inside run_analysis normally;
    # use a placeholder — the route uses its own project_id.
    return _fake_analysis_result("mock-proj")


@pytest.fixture
async def client(tmp_path: Path):
    """Test client with fake repos (no database, no agent_model)."""
    setup_test_app(tmp_path)

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test"
    ) as c:
        yield c

    app.dependency_overrides.clear()


class TestAnalyzeSSE:
    async def test_returns_sse_content_type(
        self, client: AsyncClient
    ) -> None:
        resp = await client.post(
            "/api/projects",
            json={
                "name": "test-project",
                "local_path": "tests/fixtures/test_repo",
            },
        )
        project_id = resp.json()["data"]["id"]

        with patch(
            "artifactor.api.routes.projects.run_analysis",
            new=AsyncMock(side_effect=_mock_run_analysis),
        ):
            resp = await client.post(
                f"/api/projects/{project_id}/analyze"
            )
        assert resp.status_code == 200
        content_type = resp.headers.get("content-type", "")
        assert "text/event-stream" in content_type

    async def test_nonexistent_project_returns_error(
        self, client: AsyncClient
    ) -> None:
        resp = await client.post(
            "/api/projects/nonexistent-id/analyze"
        )
        assert resp.status_code == 200
        events = _parse_sse_events(resp.text)
        error_events = [
            e for e in events if e["event"] == SSEEvent.ERROR
        ]
        assert len(error_events) >= 1
        data = json.loads(error_events[0]["data"])
        assert "not found" in data["error"].lower()

    async def test_emits_stage_events(
        self, client: AsyncClient
    ) -> None:
        resp = await client.post(
            "/api/projects",
            json={
                "name": "sse-test",
                "local_path": "tests/fixtures/test_repo",
            },
        )
        project_id = resp.json()["data"]["id"]

        with patch(
            "artifactor.api.routes.projects.run_analysis",
            new=AsyncMock(side_effect=_mock_run_analysis),
        ):
            resp = await client.post(
                f"/api/projects/{project_id}/analyze"
            )
        events = _parse_sse_events(resp.text)
        stage_events = [
            e for e in events if e["event"] == SSEEvent.STAGE
        ]
        # Should have both "running" and "done" stage events
        assert len(stage_events) >= 2

    async def test_has_complete_event(
        self, client: AsyncClient
    ) -> None:
        resp = await client.post(
            "/api/projects",
            json={
                "name": "complete-test",
                "local_path": "tests/fixtures/test_repo",
            },
        )
        project_id = resp.json()["data"]["id"]

        with patch(
            "artifactor.api.routes.projects.run_analysis",
            new=AsyncMock(side_effect=_mock_run_analysis),
        ):
            resp = await client.post(
                f"/api/projects/{project_id}/analyze"
            )
        events = _parse_sse_events(resp.text)
        complete = [
            e for e in events if e["event"] == SSEEvent.COMPLETE
        ]
        assert len(complete) == 1
        data = json.loads(complete[0]["data"])
        assert data["project_id"] == project_id
        assert "sections" in data
        assert "duration_ms" in data

    async def test_no_persistence_in_generator(
        self, client: AsyncClient
    ) -> None:
        """Persistence moved to run_analysis — generator does not call it."""
        resp = await client.post(
            "/api/projects",
            json={
                "name": "no-persist-gen",
                "local_path": "tests/fixtures/test_repo",
            },
        )
        project_id = resp.json()["data"]["id"]

        with (
            patch(
                "artifactor.api.routes.projects.run_analysis",
                new=AsyncMock(
                    side_effect=_mock_run_analysis
                ),
            ),
            patch(
                "artifactor.services.analysis_persistence"
                ".AnalysisPersistenceService"
            ) as mock_cls,
        ):
            resp = await client.post(
                f"/api/projects/{project_id}/analyze"
            )

        # Generator should NOT call AnalysisPersistenceService
        mock_cls.assert_not_called()
        events = _parse_sse_events(resp.text)
        complete = [
            e for e in events if e["event"] == SSEEvent.COMPLETE
        ]
        assert len(complete) == 1
        data = json.loads(complete[0]["data"])
        assert data["sections"] == 1

    async def test_analyze_already_running(
        self, client: AsyncClient
    ) -> None:
        """CAS guard: returns error if project is already analyzing."""
        resp = await client.post(
            "/api/projects",
            json={
                "name": "cas-test",
                "local_path": "tests/fixtures/test_repo",
            },
        )
        project_id = resp.json()["data"]["id"]

        # Manually set status to "analyzing" to simulate in-progress
        svc = app.state.project_service
        await svc.update_status(project_id, ProjectStatus.ANALYZING)

        # Second analyze request should be rejected by CAS
        resp = await client.post(
            f"/api/projects/{project_id}/analyze"
        )
        events = _parse_sse_events(resp.text)
        error_events = [
            e for e in events if e["event"] == SSEEvent.ERROR
        ]
        assert len(error_events) >= 1
        data = json.loads(error_events[0]["data"])
        assert "already in progress" in data["error"].lower()

    async def test_pause_delivers_paused_event_to_sse(
        self, client: AsyncClient
    ) -> None:
        """Pause injects 'paused' event into SSE stream."""

        resp = await client.post(
            "/api/projects",
            json={
                "name": "pause-sse-test",
                "local_path": "tests/fixtures/test_repo",
            },
        )
        project_id = resp.json()["data"]["id"]

        pause_ready = asyncio.Event()

        async def _hanging_analysis(
            repo_path,
            settings=None,
            sections=None,
            branch="main",
            on_progress=None,
            dispatcher=None,
            session_factory=None,
            project_id=None,
        ):
            if on_progress:
                on_progress(
                    StageEvent(
                        name="ingestion_resolve",
                        status=StageProgress.RUNNING,
                        message="Scanning...",
                    )
                )
            pause_ready.set()
            await asyncio.sleep(300)  # hang until cancelled
            return _fake_analysis_result("mock")

        with patch(
            "artifactor.api.routes.projects.run_analysis",
            new=AsyncMock(
                side_effect=_hanging_analysis
            ),
        ):
            analyze_task = asyncio.create_task(
                client.post(
                    f"/api/projects/{project_id}/analyze"
                )
            )
            await asyncio.wait_for(
                pause_ready.wait(), timeout=5.0
            )
            pause_resp = await client.post(
                f"/api/projects/{project_id}/pause"
            )
            assert pause_resp.json()["success"] is True

            resp = await asyncio.wait_for(
                analyze_task, timeout=5.0
            )

        events = _parse_sse_events(resp.text)
        paused_events = [
            e
            for e in events
            if e["event"] == SSEEvent.PAUSED
        ]
        assert len(paused_events) >= 1
        data = json.loads(paused_events[0]["data"])
        assert data["message"] == "Analysis paused"
