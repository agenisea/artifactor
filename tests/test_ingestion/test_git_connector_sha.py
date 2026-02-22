"""Tests for stable SHA generation in git_connector."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from artifactor.ingestion.git_connector import _get_commit_sha


@pytest.mark.asyncio
async def test_non_git_dir_gets_stable_hash(
    tmp_path: Path,
) -> None:
    """Non-git dir SHA is 40-char hex (not 'unknown')."""
    sha = await _get_commit_sha(tmp_path)
    assert sha != "unknown"
    assert len(sha) == 40
    assert re.fullmatch(r"[0-9a-f]{40}", sha)


@pytest.mark.asyncio
async def test_non_git_dir_hash_is_deterministic(
    tmp_path: Path,
) -> None:
    """Same path produces the same SHA every time."""
    sha1 = await _get_commit_sha(tmp_path)
    sha2 = await _get_commit_sha(tmp_path)
    assert sha1 == sha2
