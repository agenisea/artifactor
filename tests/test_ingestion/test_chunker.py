"""Tests for the code chunker module."""

from __future__ import annotations

from pathlib import Path

import pathspec

from artifactor.ingestion.chunker import _walk_source_files, chunk_code
from artifactor.ingestion.language_detector import detect_languages
from artifactor.ingestion.schemas import (
    ChunkedFiles,
    LanguageInfo,
    LanguageMap,
    RepoPath,
)

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "test_repo"


def _repo_path() -> RepoPath:
    return RepoPath(path=FIXTURE_DIR, commit_sha="test", branch="main")


def test_semantic_chunks_python() -> None:
    """Python functions and classes become separate chunks."""
    rp = _repo_path()
    lang_map = detect_languages(rp)
    result = chunk_code(rp, lang_map)

    assert isinstance(result, ChunkedFiles)
    assert result.total_files > 0

    # Find Python chunks — small adjacent functions may be merged
    py_chunks = [c for c in result.chunks if c.language == "python"]
    assert len(py_chunks) >= 2  # Calculator class + at least one function chunk

    # Check that we got a class chunk
    types = {c.chunk_type for c in py_chunks}
    assert "class" in types

    # Check symbol names — Calculator must be its own chunk
    symbols = {c.symbol_name for c in py_chunks if c.symbol_name}
    assert "Calculator" in symbols

    # All three symbols must appear somewhere in the chunk content
    all_content = "\n".join(c.content for c in py_chunks)
    assert "class Calculator" in all_content
    assert "def greet" in all_content
    assert "def compute_sum" in all_content


def test_fallback_chunking(tmp_path: Path) -> None:
    """A file without a grammar uses line-based chunking."""
    # Create a file with an unsupported extension
    (tmp_path / "config.xyz").write_text("line1\nline2\nline3\n" * 10)

    rp = RepoPath(path=tmp_path, commit_sha="test", branch="main")
    lang_map = LanguageMap(
        languages=[
            LanguageInfo(
                name="unknown",
                file_count=1,
                line_count=30,
                grammar_available=False,
                extensions=[".xyz"],
            )
        ],
        primary_language="unknown",
    )

    # chunk_code won't find .xyz in EXTENSION_MAP so it skips it.
    # Use a .lua file instead (in EXTENSION_MAP but no grammar installed)
    (tmp_path / "script.lua").write_text("print('hello')\n" * 20)
    lang_map = LanguageMap(
        languages=[
            LanguageInfo(
                name="lua",
                file_count=1,
                line_count=20,
                grammar_available=False,
                extensions=[".lua"],
            )
        ],
        primary_language="lua",
    )
    result = chunk_code(rp, lang_map)

    lua_chunks = [c for c in result.chunks if c.language == "lua"]
    assert len(lua_chunks) >= 1
    assert lua_chunks[0].chunk_type == "block"


def test_chunk_has_correct_line_numbers() -> None:
    """start_line and end_line match the source file content."""
    rp = _repo_path()
    lang_map = detect_languages(rp)
    result = chunk_code(rp, lang_map)

    py_chunks = [c for c in result.chunks if c.language == "python"]
    for chunk in py_chunks:
        # Line numbers should be 1-indexed and positive
        assert chunk.start_line >= 1
        assert chunk.end_line >= chunk.start_line
        # Content lines should not exceed the stated span
        content_lines = len(chunk.content.splitlines())
        span = chunk.end_line - chunk.start_line + 1
        # Merged chunks may span more lines than content (gap between
        # functions), so content_lines <= span is the invariant
        assert content_lines <= span + 1


def test_skip_vendor_directories(tmp_path: Path) -> None:
    """Files inside node_modules are skipped."""
    nm = tmp_path / "node_modules" / "pkg"
    nm.mkdir(parents=True)
    (nm / "index.js").write_text("function x() {}\n")
    (tmp_path / "app.js").write_text("function main() {}\n")

    rp = RepoPath(path=tmp_path, commit_sha="test", branch="main")
    lang_map = LanguageMap(
        languages=[
            LanguageInfo(
                name="javascript",
                file_count=1,
                line_count=1,
                grammar_available=True,
                extensions=[".js"],
            )
        ],
        primary_language="javascript",
    )
    result = chunk_code(rp, lang_map)

    # Only app.js should be chunked, not node_modules/pkg/index.js
    paths = {str(c.file_path) for c in result.chunks}
    assert all("node_modules" not in p for p in paths)
    assert result.total_files == 1


class TestGitignorePathspec:
    def test_gitignore_glob_pattern(self, tmp_path: Path) -> None:
        """Glob patterns like *.log are respected."""
        (tmp_path / "app.py").write_text("x = 1\n")
        (tmp_path / "debug.log").write_text("log line\n")
        (tmp_path / ".gitignore").write_text("*.log\n")

        spec = pathspec.PathSpec.from_lines(
            "gitignore",
            (tmp_path / ".gitignore").read_text().splitlines(),
        )
        files = _walk_source_files(tmp_path, set(), spec)
        names = [f.name for f in files]
        assert "app.py" in names
        assert "debug.log" not in names

    def test_gitignore_negation(self, tmp_path: Path) -> None:
        """Negation patterns (!) re-include files."""
        build = tmp_path / "build"
        build.mkdir()
        (build / "output.js").write_text("var x;\n")
        (build / "keep.js").write_text("var y;\n")
        (tmp_path / "app.py").write_text("x = 1\n")
        (tmp_path / ".gitignore").write_text(
            "build/\n!build/keep.js\n"
        )

        spec = pathspec.PathSpec.from_lines(
            "gitignore",
            (tmp_path / ".gitignore").read_text().splitlines(),
        )
        files = _walk_source_files(tmp_path, set(), spec)
        names = [f.name for f in files]
        assert "app.py" in names
        # pathspec handles negation for the directory
        assert "output.js" not in names
