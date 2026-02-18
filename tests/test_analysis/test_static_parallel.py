"""Tests for parallel static analysis execution."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from artifactor.analysis.static.analyzer import run_static_analysis
from artifactor.analysis.static.schemas import (
    ASTForest,
    CallGraph,
    StaticAnalysisResult,
)
from artifactor.ingestion.chunker import chunk_code
from artifactor.ingestion.language_detector import detect_languages
from artifactor.ingestion.schemas import RepoPath

FIXTURE_DIR = (
    Path(__file__).resolve().parent.parent
    / "fixtures"
    / "test_repo"
)


async def test_parallel_returns_all_results() -> None:
    """All 5 result fields should be populated."""
    rp = RepoPath(
        path=FIXTURE_DIR, commit_sha="test", branch="main"
    )
    lm = detect_languages(rp)
    cf = chunk_code(rp, lm)

    result = await run_static_analysis(rp, cf, lm)

    assert isinstance(result, StaticAnalysisResult)
    assert isinstance(result.ast_forest, ASTForest)
    assert isinstance(result.call_graph, CallGraph)


async def test_one_module_fails_others_succeed() -> None:
    """If one module raises, others still produce output."""
    rp = RepoPath(
        path=FIXTURE_DIR, commit_sha="test", branch="main"
    )
    lm = detect_languages(rp)
    cf = chunk_code(rp, lm)

    with patch(
        "artifactor.analysis.static.analyzer.build_call_graph",
        side_effect=RuntimeError("call graph boom"),
    ):
        result = await run_static_analysis(rp, cf, lm)

    # Call graph should be empty fallback
    assert len(result.call_graph.edges) == 0
    # But AST forest should still work
    assert len(result.ast_forest.entities) > 0
    # And schema map should still work
    assert len(result.schema_map.entities) > 0


async def test_ast_failure_gives_empty_downstream() -> None:
    """If AST parsing fails, downstream modules get empty ASTForest."""
    rp = RepoPath(
        path=FIXTURE_DIR, commit_sha="test", branch="main"
    )
    lm = detect_languages(rp)
    cf = chunk_code(rp, lm)

    with patch(
        "artifactor.analysis.static.analyzer.parse_asts",
        side_effect=RuntimeError("ast boom"),
    ):
        result = await run_static_analysis(rp, cf, lm)

    # AST forest should be empty fallback
    assert len(result.ast_forest.entities) == 0
    # But dependency graph (doesn't need AST) should still work
    assert result.dependency_graph is not None
