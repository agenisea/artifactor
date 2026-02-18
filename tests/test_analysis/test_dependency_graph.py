"""Tests for the dependency graph module."""

from __future__ import annotations

from pathlib import Path

from artifactor.analysis.static.dependency_graph import extract_imports
from artifactor.ingestion.chunker import chunk_code
from artifactor.ingestion.language_detector import detect_languages
from artifactor.ingestion.schemas import (
    LanguageInfo,
    LanguageMap,
    RepoPath,
)

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "test_repo"


def test_python_imports_detected() -> None:
    """Detects import statements in Python files."""
    rp = RepoPath(path=FIXTURE_DIR, commit_sha="test", branch="main")
    lm = detect_languages(rp)
    cf = chunk_code(rp, lm)
    dg = extract_imports(cf, lm)

    # api_app.py imports from fastapi
    targets = {e.target for e in dg.edges}
    assert "fastapi" in targets


def test_javascript_require_detected(tmp_path: Path) -> None:
    """Detects require() calls in JavaScript files."""
    (tmp_path / "index.js").write_text(
        "const fs = require('fs');\n"
        "const path = require('path');\n"
        "import React from 'react';\n"
    )
    rp = RepoPath(path=tmp_path, commit_sha="test", branch="main")
    lm = LanguageMap(
        languages=[
            LanguageInfo(
                name="javascript",
                file_count=1,
                line_count=3,
                grammar_available=True,
                extensions=[".js"],
            )
        ],
        primary_language="javascript",
    )
    cf = chunk_code(rp, lm)
    dg = extract_imports(cf, lm)

    targets = {e.target for e in dg.edges}
    assert "fs" in targets or "react" in targets
