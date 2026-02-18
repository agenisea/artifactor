"""Tests for the git connector module."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from artifactor.ingestion.git_connector import (
    _dir_size,
    _rev_parse,
    resolve_local_repo,
)
from artifactor.ingestion.schemas import RepoPath, RepoSource

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "test_repo"


@pytest.fixture
def fixture_repo() -> Path:
    """Return the path to the test_repo fixture."""
    assert FIXTURE_DIR.is_dir(), f"Missing fixture: {FIXTURE_DIR}"
    return FIXTURE_DIR


async def test_use_local_path(fixture_repo: Path) -> None:
    """Using a local dir returns a RepoPath pointing at the original."""
    source = RepoSource(local_path=fixture_repo)
    result = await resolve_local_repo(source)

    assert isinstance(result, RepoPath)
    assert result.path == fixture_repo.resolve()
    assert result.branch == "main"
    assert isinstance(result.commit_sha, str)


async def test_local_path_not_found() -> None:
    """A non-existent local_path raises FileNotFoundError."""
    source = RepoSource(local_path=Path("/tmp/nonexistent_artifactor_test"))
    with pytest.raises(FileNotFoundError):
        await resolve_local_repo(source)


async def test_rev_parse_timeout_returns_unknown(
    tmp_path: Path,
) -> None:
    """When git rev-parse hangs, _rev_parse returns 'unknown'."""

    async def _hang_communicate() -> tuple[bytes, bytes]:
        await asyncio.sleep(60)
        return b"", b""

    mock_proc = AsyncMock()
    mock_proc.communicate = _hang_communicate
    mock_proc.kill = MagicMock()

    with patch(
        "artifactor.ingestion.git_connector"
        ".asyncio.create_subprocess_exec",
        return_value=mock_proc,
    ):
        result = await _rev_parse(tmp_path)

    assert result == "unknown"
    mock_proc.kill.assert_called_once()


def test_dir_size_skips_directories(tmp_path: Path) -> None:
    """_dir_size with skip_dirs excludes matching directories."""
    # Create source files
    src = tmp_path / "src"
    src.mkdir()
    (src / "main.py").write_text("print('hello')")

    # Create node_modules (should be skipped)
    nm = tmp_path / "node_modules"
    nm.mkdir()
    (nm / "big.js").write_text("x" * 10000)

    total_with_skip = _dir_size(tmp_path, skip_dirs={"node_modules"})
    total_without_skip = _dir_size(tmp_path)

    assert total_with_skip < total_without_skip
    # Only src/main.py should be counted
    assert total_with_skip == len("print('hello')")


def test_dir_size_ignores_broken_symlinks(tmp_path: Path) -> None:
    """_dir_size doesn't crash on broken symlinks."""
    (tmp_path / "real.txt").write_text("data")
    broken = tmp_path / "broken_link"
    os.symlink("/nonexistent/path", broken)

    # Should not raise
    total = _dir_size(tmp_path)
    assert total == len("data")


def test_dir_size_symlinks_not_counted(tmp_path: Path) -> None:
    """_dir_size excludes symlinks (even valid ones) from the count."""
    (tmp_path / "real.txt").write_text("content")
    os.symlink(tmp_path / "real.txt", tmp_path / "link.txt")

    total = _dir_size(tmp_path)
    # Only the real file, not the symlink
    assert total == len("content")
