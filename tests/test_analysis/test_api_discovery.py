"""Tests for the API discovery module."""

from __future__ import annotations

from pathlib import Path

from artifactor.analysis.static.api_discovery import discover_endpoints
from artifactor.analysis.static.ast_parser import parse_asts
from artifactor.ingestion.chunker import chunk_code
from artifactor.ingestion.language_detector import detect_languages
from artifactor.ingestion.schemas import RepoPath

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "test_repo"


def test_fastapi_endpoint_detected() -> None:
    """Finds FastAPI route decorators from api_app.py fixture."""
    rp = RepoPath(path=FIXTURE_DIR, commit_sha="test", branch="main")
    lm = detect_languages(rp)
    cf = chunk_code(rp, lm)
    af = parse_asts(cf, lm)
    ep = discover_endpoints(af, cf, lm)

    methods = {e.method for e in ep.endpoints}
    paths = {e.path for e in ep.endpoints}

    assert "GET" in methods
    assert "POST" in methods
    assert "/api/health" in paths
    assert "/api/users" in paths

    # Check handler names resolved
    for endpoint in ep.endpoints:
        assert endpoint.handler_function != "unknown"
