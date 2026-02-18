"""Tests for the static analysis orchestrator."""

from __future__ import annotations

from pathlib import Path

from artifactor.analysis.static.analyzer import run_static_analysis
from artifactor.analysis.static.schemas import StaticAnalysisResult
from artifactor.ingestion.chunker import chunk_code
from artifactor.ingestion.language_detector import detect_languages
from artifactor.ingestion.schemas import RepoPath

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "test_repo"


async def test_run_static_analysis_returns_result() -> None:
    """Full pipeline produces a StaticAnalysisResult with populated fields."""
    rp = RepoPath(path=FIXTURE_DIR, commit_sha="test", branch="main")
    lm = detect_languages(rp)
    cf = chunk_code(rp, lm)

    result = await run_static_analysis(rp, cf, lm)

    assert isinstance(result, StaticAnalysisResult)
    # AST forest should have entities
    assert len(result.ast_forest.entities) > 0
    # Schema map should have tables from schema.sql
    assert len(result.schema_map.entities) > 0
    # API endpoints should have routes from api_app.py
    assert len(result.api_endpoints.endpoints) > 0
