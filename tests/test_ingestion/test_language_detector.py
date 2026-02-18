"""Tests for the language detector module."""

from __future__ import annotations

from pathlib import Path

from artifactor.ingestion.language_detector import detect_languages
from artifactor.ingestion.schemas import LanguageMap, RepoPath

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "test_repo"


def _repo_path() -> RepoPath:
    return RepoPath(path=FIXTURE_DIR, commit_sha="test", branch="main")


def test_detect_python_and_javascript() -> None:
    """Both Python and JavaScript are detected in the test repo."""
    result = detect_languages(_repo_path())
    assert isinstance(result, LanguageMap)
    names = {li.name for li in result.languages}
    assert "python" in names
    assert "javascript" in names


def test_primary_language() -> None:
    """Primary language is the one with the most lines."""
    result = detect_languages(_repo_path())
    assert result.primary_language is not None
    # Python file has more lines than JS in our fixture
    assert result.primary_language == "python"


def test_skip_binary_files(tmp_path: Path) -> None:
    """Binary files are excluded from language counts."""
    # Create one text file and one binary file (with null bytes)
    (tmp_path / "app.py").write_text("x = 1\n")
    (tmp_path / "image.py").write_bytes(b"\x00\x89PNG\r\n" + b"\x00" * 100)

    rp = RepoPath(path=tmp_path, commit_sha="test", branch="main")
    result = detect_languages(rp)

    # Only app.py should be counted — image.py is binary
    assert len(result.languages) == 1
    assert result.languages[0].name == "python"
    assert result.languages[0].file_count == 1


def test_skip_hidden_dirs(tmp_path: Path) -> None:
    """Hidden directories like .git are not scanned."""
    # Create a mini repo with a .git dir containing a .py file
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "hook.py").write_text("x = 1\n")
    (tmp_path / "app.py").write_text("def main(): pass\n")

    rp = RepoPath(path=tmp_path, commit_sha="test", branch="main")
    result = detect_languages(rp)

    # Only the top-level app.py should be found (1 file)
    assert len(result.languages) == 1
    assert result.languages[0].file_count == 1


def test_unknown_extension(tmp_path: Path) -> None:
    """Files with unrecognized extensions are counted as 'unknown'."""
    (tmp_path / "data.xyz").write_text("some content\n")

    rp = RepoPath(path=tmp_path, commit_sha="test", branch="main")
    result = detect_languages(rp)

    names = {li.name for li in result.languages}
    assert "unknown" in names
    unknown = next(li for li in result.languages if li.name == "unknown")
    assert unknown.grammar_available is False
