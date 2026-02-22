"""Integration: static-only pipeline on test_repo fixture.

Runs the full analysis pipeline (without LLM) against
tests/fixtures/test_repo and verifies 13 sections are produced.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from artifactor.config import Settings
from artifactor.constants import StageProgress
from artifactor.services.analysis_service import run_analysis
from artifactor.services.events import StageEvent

_TEST_REPO = Path(__file__).resolve().parents[1] / "fixtures" / "test_repo"


@pytest.fixture
def settings() -> Settings:
    """Settings with demo API key — no real LLM calls."""
    return Settings(
        anthropic_api_key="for-demo-purposes-only",
        openai_api_key="for-demo-purposes-only",
    )


async def test_pipeline_completes(settings: Settings, tmp_path: Path) -> None:
    """Full pipeline completes without exceptions."""
    result = await run_analysis(
        repo_path=_TEST_REPO,
        settings=settings,
    )
    assert all(s.ok for s in result.stages), [
        s for s in result.stages if not s.ok
    ]


async def test_13_sections_generated(settings: Settings) -> None:
    """All 13 section generators produce output."""
    result = await run_analysis(
        repo_path=_TEST_REPO,
        settings=settings,
    )
    assert len(result.sections) == 13


async def test_sections_have_content(settings: Settings) -> None:
    """Every generated section has non-empty content."""
    result = await run_analysis(
        repo_path=_TEST_REPO,
        settings=settings,
    )
    for section in result.sections:
        assert section.content.strip(), (
            f"Section {section.section_name} has empty content"
        )


async def test_intelligence_model_built(settings: Settings) -> None:
    """Intelligence model is populated from static analysis."""
    result = await run_analysis(
        repo_path=_TEST_REPO,
        settings=settings,
    )
    assert result.model is not None
    # test_repo has Calculator class + functions
    assert len(result.model.knowledge_graph.entities) > 0


async def test_static_entities_detected(settings: Settings) -> None:
    """Known entities from test_repo are discovered."""
    result = await run_analysis(
        repo_path=_TEST_REPO,
        settings=settings,
    )
    assert result.model is not None
    names = {
        e.name
        for e in result.model.knowledge_graph.entities.values()
    }
    # main.py has Calculator, greet, compute_sum
    assert "Calculator" in names
    assert "greet" in names
    # utils.js has formatDate, slugify
    assert "formatDate" in names


async def test_progress_callback_fires(settings: Settings) -> None:
    """on_progress callback is called for each phase."""
    events: list[StageEvent] = []
    await run_analysis(
        repo_path=_TEST_REPO,
        settings=settings,
        on_progress=events.append,
    )
    # Each stage emits "running" + "done"/"error" = at least 2 events per stage
    assert len(events) >= 12
    running = [e for e in events if e.status == StageProgress.RUNNING]
    done = [e for e in events if e.status == StageProgress.DONE]
    assert len(running) >= 6
    assert len(done) >= 6
    assert any("repository" in e.message.lower() for e in running)
    assert any("ast" in e.message.lower() for e in running)
