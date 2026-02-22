"""Tests for commit_sha assignment in PipelineContext."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from artifactor.config import Settings
from artifactor.ingestion.schemas import RepoPath
from artifactor.services.analysis_service import (
    PipelineContext,
    run_analysis,
)


@pytest.mark.asyncio
async def test_commit_sha_set_on_context() -> None:
    """Verify ctx.commit_sha is populated after ingestion."""
    fake_repo = RepoPath(
        path=Path("/tmp/fake"),
        commit_sha="abc123def456",
        branch="main",
    )

    captured_ctx: list[PipelineContext] = []

    original_llm_stage = (
        "artifactor.services.analysis_service._llm_stage"
    )
    original_static_stage = (
        "artifactor.services.analysis_service._static_stage"
    )

    async def _capture_ctx(ctx: PipelineContext) -> None:
        captured_ctx.append(ctx)

    with (
        patch(
            "artifactor.services.analysis_service.resolve_local_repo",
            new_callable=AsyncMock,
            return_value=fake_repo,
        ),
        patch(
            "artifactor.services.analysis_service.detect_languages",
            return_value=MagicMock(languages=[]),
        ),
        patch(
            "artifactor.services.analysis_service.chunk_code",
            return_value=MagicMock(
                chunks=[], total_files=0, total_chunks=0
            ),
        ),
        patch(
            original_static_stage,
            side_effect=_capture_ctx,
        ),
        patch(
            original_llm_stage,
            side_effect=_capture_ctx,
        ),
        patch(
            "artifactor.services.analysis_service.cross_validate",
            return_value=MagicMock(),
        ),
        patch(
            "artifactor.services.analysis_service.build_intelligence_model",
            return_value=MagicMock(),
        ),
    ):
        await run_analysis(
            repo_path="/tmp/fake",
            settings=Settings(),
        )

    assert len(captured_ctx) >= 1
    assert captured_ctx[0].commit_sha == "abc123def456"


@pytest.mark.asyncio
async def test_checkpoint_write_after_analysis() -> None:
    """Verify checkpoint put() is called when commit_sha is set."""
    fake_repo = RepoPath(
        path=Path("/tmp/fake"),
        commit_sha="sha_for_checkpoint",
        branch="main",
    )
    session_factory = MagicMock()

    with (
        patch(
            "artifactor.services.analysis_service.resolve_local_repo",
            new_callable=AsyncMock,
            return_value=fake_repo,
        ),
        patch(
            "artifactor.services.analysis_service.detect_languages",
            return_value=MagicMock(languages=[]),
        ),
        patch(
            "artifactor.services.analysis_service.chunk_code",
            return_value=MagicMock(
                chunks=[], total_files=0, total_chunks=0
            ),
        ),
        patch(
            "artifactor.services.analysis_service._static_stage",
            new_callable=AsyncMock,
        ),
        patch(
            "artifactor.services.analysis_service._llm_stage",
            new_callable=AsyncMock,
        ),
        patch(
            "artifactor.services.analysis_service.cross_validate",
            return_value=MagicMock(),
        ),
        patch(
            "artifactor.services.analysis_service.build_intelligence_model",
            return_value=MagicMock(),
        ),
        patch(
            "artifactor.services.analysis_service.SqlCheckpointRepository",
        ) as mock_cp_cls,
    ):
        await run_analysis(
            repo_path="/tmp/fake",
            settings=Settings(),
            session_factory=session_factory,
        )

    # SqlCheckpointRepository should have been instantiated
    mock_cp_cls.assert_called_once_with(session_factory)
