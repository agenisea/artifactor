"""Tests for extracted pipeline phase functions."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from artifactor.config import Settings
from artifactor.ingestion.schemas import (
    ChunkedFiles,
    CodeChunk,
    LanguageMap,
    RepoPath,
)
from artifactor.services.analysis_service import (
    AnalysisResult,
    PipelineContext,
    _phase_citation_verification,
    _phase_dual_analysis,
    _phase_ingestion,
    _phase_persistence,
    _phase_quality,
    _phase_section_generation,
)
from artifactor.services.events import StageEvent


def _make_ctx(**overrides: object) -> PipelineContext:
    """Create a PipelineContext with sensible defaults."""
    defaults = {
        "project_id": "p1",
        "repo_path": Path("/tmp/repo"),
        "settings": Settings(),
    }
    defaults.update(overrides)
    return PipelineContext(**defaults)  # pyright: ignore[reportArgumentType]


@pytest.mark.asyncio
async def test_phase_ingestion_success() -> None:
    """Ingestion sets ctx.repo, ctx.lang_map, ctx.chunks."""
    events: list[StageEvent] = []
    ctx = _make_ctx(on_progress=lambda e: events.append(e))
    result = AnalysisResult(project_id="p1")

    fake_repo = RepoPath(
        path=Path("/tmp/repo"),
        commit_sha="abc123",
        branch="main",
    )
    fake_lang_map = LanguageMap()
    fake_chunks = ChunkedFiles(
        chunks=[
            CodeChunk(
                file_path="test.py",
                content="x = 1",
                language="python",
                chunk_type="module",
                start_line=1,
                end_line=1,
            )
        ],
        total_files=1,
        total_chunks=1,
    )

    with (
        patch(
            "artifactor.services.analysis_service.resolve_local_repo",
            new_callable=AsyncMock,
            return_value=fake_repo,
        ),
        patch(
            "artifactor.services.analysis_service.detect_languages",
            return_value=fake_lang_map,
        ),
        patch(
            "artifactor.services.analysis_service.chunk_code",
            return_value=fake_chunks,
        ),
    ):
        ok = await _phase_ingestion(ctx, result)

    assert ok is True
    assert ctx.repo is fake_repo
    assert ctx.lang_map is fake_lang_map
    assert ctx.chunks is fake_chunks
    assert ctx.commit_sha == "abc123"
    assert len(result.stages) == 3  # resolve, detect, chunk
    assert len(events) >= 3


@pytest.mark.asyncio
async def test_phase_ingestion_failure() -> None:
    """Returns False when repo resolution fails."""
    ctx = _make_ctx()
    result = AnalysisResult(project_id="p1")

    with patch(
        "artifactor.services.analysis_service.resolve_local_repo",
        new_callable=AsyncMock,
        side_effect=RuntimeError("not a repo"),
    ):
        ok = await _phase_ingestion(ctx, result)

    assert ok is False
    assert ctx.repo is None
    assert len(result.stages) == 1
    assert result.stages[0].ok is False


@pytest.mark.asyncio
async def test_phase_dual_analysis() -> None:
    """Sets ctx.static and ctx.llm."""
    ctx = _make_ctx(
        chunks=ChunkedFiles(
            chunks=[], total_files=0, total_chunks=0
        ),
    )
    result = AnalysisResult(project_id="p1")

    with (
        patch(
            "artifactor.services.analysis_service._static_stage",
            new_callable=AsyncMock,
        ),
        patch(
            "artifactor.services.analysis_service._llm_stage",
            new_callable=AsyncMock,
        ),
    ):
        await _phase_dual_analysis(ctx, result)

    # Should have set defaults when stages don't write
    assert ctx.static is not None
    assert ctx.llm is not None
    assert len(result.stages) == 2


@pytest.mark.asyncio
async def test_phase_quality_builds_model() -> None:
    """Sets ctx.model and ctx.validation."""
    ctx = _make_ctx()
    result = AnalysisResult(project_id="p1")

    fake_model = MagicMock()
    with (
        patch(
            "artifactor.services.analysis_service.cross_validate",
            return_value=MagicMock(),
        ),
        patch(
            "artifactor.services.analysis_service.build_intelligence_model",
            return_value=fake_model,
        ),
    ):
        ok = await _phase_quality(ctx, result)

    assert ok is True
    assert ctx.model is fake_model
    assert result.model is fake_model
    assert ctx.validation is not None
    assert len(result.stages) == 2  # quality + model


@pytest.mark.asyncio
async def test_phase_quality_fails_without_model() -> None:
    """Returns False when model build returns None."""
    ctx = _make_ctx()
    result = AnalysisResult(project_id="p1")

    with (
        patch(
            "artifactor.services.analysis_service.cross_validate",
            return_value=MagicMock(),
        ),
        patch(
            "artifactor.services.analysis_service.build_intelligence_model",
            side_effect=RuntimeError("model build failed"),
        ),
    ):
        ok = await _phase_quality(ctx, result)

    assert ok is False
    assert ctx.model is None


@pytest.mark.asyncio
async def test_phase_section_generation() -> None:
    """Populates result.sections."""
    from artifactor.outputs.base import SectionOutput

    fake_model = MagicMock()
    ctx = _make_ctx(model=fake_model)
    result = AnalysisResult(project_id="p1")

    fake_output = SectionOutput(
        title="Overview",
        section_name="executive_overview",
        content="# Overview\nTest.",
        confidence=0.9,
    )

    with patch(
        "artifactor.services.analysis_service.SECTION_GENERATORS",
        {"executive_overview": AsyncMock(return_value=fake_output)},
    ):
        await _phase_section_generation(
            ctx, result, ["executive_overview"]
        )

    assert len(result.sections) >= 1


@pytest.mark.asyncio
async def test_phase_citation_verification() -> None:
    """Sets result.quality_report when citations exist."""
    from artifactor.analysis.quality.schemas import (
        GuardrailResult,
    )
    from artifactor.outputs.base import SectionOutput

    ctx = _make_ctx()
    section = SectionOutput(
        title="Test",
        section_name="test_section",
        content="content",
        confidence=0.9,
        citations=["src/main.py:10"],
    )
    result = AnalysisResult(
        project_id="p1", sections=[section]
    )

    fake_guardrails = [
        GuardrailResult(
            check_name="citation_exists",
            passed=True,
        )
    ]
    with patch(
        "artifactor.services.analysis_service.verify_citations",
        return_value=fake_guardrails,
    ):
        await _phase_citation_verification(ctx, result)

    assert result.quality_report is not None
    assert result.quality_report.citations_checked == 1
    assert result.quality_report.citations_valid == 1


@pytest.mark.asyncio
async def test_phase_citation_skips_when_no_citations() -> None:
    """No-op when sections have no citations."""
    ctx = _make_ctx()
    result = AnalysisResult(project_id="p1")

    await _phase_citation_verification(ctx, result)

    assert result.quality_report is None
    assert len(result.stages) == 0


@pytest.mark.asyncio
async def test_phase_persistence() -> None:
    """Calls AnalysisPersistenceService.persist()."""
    ctx = _make_ctx(session_factory=MagicMock())
    result = AnalysisResult(project_id="p1")

    with patch(
        "artifactor.services.analysis_persistence.AnalysisPersistenceService"
    ) as mock_cls:
        mock_svc = AsyncMock()
        mock_cls.return_value = mock_svc
        await _phase_persistence(ctx, result)

    mock_svc.persist.assert_awaited_once_with("p1", result)


@pytest.mark.asyncio
async def test_phase_persistence_skips_without_session() -> None:
    """No-op when session_factory is None."""
    ctx = _make_ctx()
    result = AnalysisResult(project_id="p1")

    # Should not raise
    await _phase_persistence(ctx, result)
