"""Tests for checkpoint logging and dead-code cleanup in analyzer."""

from __future__ import annotations

import ast
import inspect
import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from artifactor.analysis.llm.analyzer import (
    _chunk_hash,
    _serialize_result,
    run_llm_analysis,
)
from artifactor.analysis.llm.schemas import (
    ModuleNarrative,
)
from artifactor.config import Settings
from artifactor.ingestion.schemas import ChunkedFiles, CodeChunk, LanguageMap


def _make_chunk(
    file_path: str = "test.py",
    content: str = "def foo(): pass",
    language: str = "python",
) -> CodeChunk:
    return CodeChunk(
        file_path=file_path,
        content=content,
        language=language,
        chunk_type="function",
        start_line=1,
        end_line=1,
    )


@pytest.mark.asyncio
async def test_checkpoint_hit_logs_debug(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify event=checkpoint_hit appears in debug log."""
    chunk = _make_chunk()
    _chunk_hash(chunk)

    narrative = ModuleNarrative(
        file_path="test.py",
        purpose="test",
        confidence="high",
    )
    result_json = _serialize_result(
        (narrative, [], []), "test.py"
    )

    checkpoint = MagicMock()
    checkpoint.result_json = result_json

    repo = AsyncMock()
    repo.get.return_value = checkpoint

    settings = Settings()
    chunked = ChunkedFiles(
        chunks=[chunk], total_files=1, total_chunks=1
    )
    lang_map = LanguageMap()

    with caplog.at_level(logging.DEBUG):
        await run_llm_analysis(
            chunked,
            lang_map,
            settings,
            checkpoint_repo=repo,
            commit_sha="abc123",
            project_id="proj-1",
        )

    assert "checkpoint_hit" in caplog.text
    assert "test.py" in caplog.text


def test_no_dead_pre_gather_log() -> None:
    """Verify the dead pre-gather 'checkpoint_resume' log was removed.

    The old code had a `if resumed_count > 0` check before
    asyncio.gather — but tasks weren't awaited yet so
    resumed_count was always 0. That dead log is now removed.
    """
    source = inspect.getsource(run_llm_analysis)
    tree = ast.parse(source)

    log_calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr in (
                "info",
                "debug",
                "warning",
            ):
                for arg in node.args:
                    if (
                        isinstance(arg, ast.Constant)
                        and isinstance(arg.value, str)
                        and "checkpoint_resume" in arg.value
                    ):
                        log_calls.append(arg.value)

    # Only the post-gather log should remain
    assert len(log_calls) == 1
    assert "checkpoint_resume_complete" in log_calls[0]


@pytest.mark.asyncio
async def test_checkpoint_round_trip() -> None:
    """Write checkpoint, re-run, verify LLM call skipped."""
    chunk = _make_chunk(content="x = 1")
    c_hash = _chunk_hash(chunk)

    narrative = ModuleNarrative(
        file_path="test.py",
        purpose="test var",
        confidence="high",
    )
    result_json = _serialize_result(
        (narrative, [], []), "test.py"
    )

    # First run: no checkpoint, should call analyze_chunk
    stored: dict[str, MagicMock] = {}

    repo = AsyncMock()
    repo.get.return_value = None

    async def _put(cp: object) -> None:
        stored[getattr(cp, "chunk_hash", "")] = cp

    repo.put.side_effect = _put

    settings = Settings()
    chunked = ChunkedFiles(
        chunks=[chunk], total_files=1, total_chunks=1
    )
    lang_map = LanguageMap()

    # Mock analyze_chunk to return known result
    from unittest.mock import patch

    mock_result = (narrative, [], [])
    with patch(
        "artifactor.analysis.llm.analyzer.analyze_chunk",
        new_callable=AsyncMock,
        return_value=mock_result,
    ) as mock_analyze:
        await run_llm_analysis(
            chunked,
            lang_map,
            settings,
            checkpoint_repo=repo,
            commit_sha="sha1",
            project_id="proj-1",
        )
        assert mock_analyze.await_count == 1

    # Verify checkpoint was written
    assert c_hash in stored

    # Second run: checkpoint exists, should skip analyze_chunk
    checkpoint = MagicMock()
    checkpoint.result_json = result_json
    repo.get.return_value = checkpoint

    with patch(
        "artifactor.analysis.llm.analyzer.analyze_chunk",
        new_callable=AsyncMock,
    ) as mock_analyze2:
        result = await run_llm_analysis(
            chunked,
            lang_map,
            settings,
            checkpoint_repo=repo,
            commit_sha="sha1",
            project_id="proj-1",
        )
        # analyze_chunk should NOT have been called
        assert mock_analyze2.await_count == 0

    assert len(result.narratives) == 1
    assert result.narratives[0].purpose == "test var"
