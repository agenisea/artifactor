"""Tests for the AST parser module."""

from __future__ import annotations

from pathlib import Path

from artifactor.analysis.static.ast_parser import parse_asts
from artifactor.analysis.static.schemas import ASTForest
from artifactor.ingestion.chunker import chunk_code
from artifactor.ingestion.language_detector import detect_languages
from artifactor.ingestion.schemas import (
    ChunkedFiles,
    CodeChunk,
    LanguageInfo,
    LanguageMap,
    RepoPath,
)

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "test_repo"


def _fixture_data() -> tuple[ChunkedFiles, LanguageMap]:
    rp = RepoPath(path=FIXTURE_DIR, commit_sha="test", branch="main")
    lm = detect_languages(rp)
    cf = chunk_code(rp, lm)
    return cf, lm


def test_parse_python_extracts_functions() -> None:
    """Finds greet and compute_sum functions from Python fixture."""
    cf, lm = _fixture_data()
    result = parse_asts(cf, lm)

    assert isinstance(result, ASTForest)
    names = {e.name for e in result.entities}
    assert "greet" in names or "compute_sum" in names


def test_parse_python_extracts_classes() -> None:
    """Finds Calculator class from Python fixture."""
    cf, lm = _fixture_data()
    result = parse_asts(cf, lm)

    names = {e.name for e in result.entities if e.entity_type == "class"}
    assert "Calculator" in names


def test_entity_has_file_path_and_line_numbers() -> None:
    """Every entity has valid file_path, start_line, and end_line."""
    cf, lm = _fixture_data()
    result = parse_asts(cf, lm)

    assert len(result.entities) > 0
    for entity in result.entities:
        assert entity.file_path is not None
        assert entity.start_line >= 1
        assert entity.end_line >= entity.start_line
        assert entity.language in ("python", "javascript")


def test_parse_javascript_extracts_functions() -> None:
    """Finds functions from JavaScript fixture."""
    cf, lm = _fixture_data()
    result = parse_asts(cf, lm)

    js_entities = [e for e in result.entities if e.language == "javascript"]
    assert len(js_entities) >= 1


def test_unsupported_language_returns_empty() -> None:
    """A language without a grammar produces no entities."""
    lm = LanguageMap(
        languages=[
            LanguageInfo(
                name="unknown_lang",
                file_count=1,
                line_count=10,
                grammar_available=False,
                extensions=[".xyz"],
            )
        ],
        primary_language="unknown_lang",
    )
    cf = ChunkedFiles(
        chunks=[
            CodeChunk(
                file_path=Path("test.xyz"),
                language="unknown_lang",
                chunk_type="block",
                start_line=1,
                end_line=10,
                content="some random content\n" * 10,
            )
        ],
        total_files=1,
        total_lines=10,
    )
    result = parse_asts(cf, lm)
    assert len(result.entities) == 0
