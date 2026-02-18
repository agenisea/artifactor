"""Tests for pipeline persistence (Phase 7 in run_analysis)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from artifactor.analysis.llm.schemas import LLMAnalysisResult
from artifactor.analysis.static.schemas import StaticAnalysisResult
from artifactor.config import Settings
from artifactor.ingestion.schemas import (
    ChunkedFiles,
    LanguageMap,
    RepoPath,
)
from artifactor.services.analysis_service import run_analysis


@pytest.fixture
def mock_pipeline():
    """Mock all heavy pipeline stages so run_analysis reaches Phase 7."""
    with (
        patch(
            "artifactor.services.analysis_service.resolve_local_repo",
            new_callable=AsyncMock,
            return_value=RepoPath(
                path=Path("/tmp/test"),
                commit_sha="abc123",
                branch="main",
            ),
        ),
        patch(
            "artifactor.services.analysis_service.detect_languages",
            return_value=LanguageMap(),
        ),
        patch(
            "artifactor.services.analysis_service.chunk_code",
            return_value=ChunkedFiles(),
        ),
        patch(
            "artifactor.services.analysis_service.run_static_analysis",
            new_callable=AsyncMock,
            return_value=StaticAnalysisResult(),
        ),
        patch(
            "artifactor.services.analysis_service.run_llm_analysis",
            new_callable=AsyncMock,
            return_value=LLMAnalysisResult(),
        ),
    ):
        yield


async def test_run_analysis_persists_when_session_factory_set(
    mock_pipeline: None,
) -> None:
    """Phase 7: persistence runs when session_factory is provided."""
    mock_persist = AsyncMock()
    mock_sf = MagicMock()

    with patch(
        "artifactor.services.analysis_persistence"
        ".AnalysisPersistenceService"
    ) as mock_cls:
        mock_cls.return_value.persist = mock_persist
        result = await run_analysis(
            repo_path="/tmp/test",
            settings=Settings(
                database_url="sqlite:///:memory:"
            ),
            session_factory=mock_sf,
            project_id="test-persist",
        )

    mock_cls.assert_called_once_with(mock_sf)
    mock_persist.assert_called_once_with("test-persist", result)


async def test_run_analysis_no_persist_without_session_factory(
    mock_pipeline: None,
) -> None:
    """Phase 7: persistence is skipped when session_factory is None."""
    with patch(
        "artifactor.services.analysis_persistence"
        ".AnalysisPersistenceService"
    ) as mock_cls:
        result = await run_analysis(
            repo_path="/tmp/test",
            settings=Settings(
                database_url="sqlite:///:memory:"
            ),
            session_factory=None,
            project_id="test-no-persist",
        )

    mock_cls.assert_not_called()
    assert result.project_id == "test-no-persist"
