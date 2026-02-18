"""Resolve a local repository for analysis."""

from __future__ import annotations

import asyncio
import contextlib
from pathlib import Path

from artifactor.config import Settings
from artifactor.constants import GIT_REVPARSE_TIMEOUT
from artifactor.ingestion.schemas import RepoPath, RepoSource


async def resolve_local_repo(
    source: RepoSource,
    settings: Settings | object | None = None,
) -> RepoPath:
    """Resolve a local directory for analysis.

    Validates the path exists, checks size limits, and
    returns a :class:`RepoPath` with the resolved commit SHA.
    """
    if settings is None:
        settings = Settings()
    cfg = settings if isinstance(settings, Settings) else Settings()

    max_size = cfg.max_repo_size_bytes

    return await _use_local(
        source.local_path,
        source.branch,
        max_size,
        skip_dirs=set(cfg.skip_directories),
    )


async def _use_local(
    local_path: Path,
    branch: str,
    max_size: int,
    skip_dirs: set[str] | None = None,
) -> RepoPath:
    """Use a local directory in-place (read-only analysis)."""
    src = Path(local_path).resolve()
    if not src.is_dir():
        msg = f"Local path does not exist: {src}"
        raise FileNotFoundError(msg)

    total = _dir_size(src, skip_dirs=skip_dirs or set())
    if total > max_size:
        msg = f"Repository exceeds max size ({total} > {max_size} bytes)"
        raise ValueError(msg)

    sha = await _get_commit_sha(src)
    return RepoPath(path=src, commit_sha=sha, branch=branch)


async def _rev_parse(repo_dir: Path) -> str:
    """Get HEAD commit SHA from a git repo."""
    proc = await asyncio.create_subprocess_exec(
        "git",
        "-C",
        str(repo_dir),
        "rev-parse",
        "HEAD",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, _ = await asyncio.wait_for(
            proc.communicate(), timeout=GIT_REVPARSE_TIMEOUT
        )
    except TimeoutError:
        proc.kill()
        return "unknown"
    if proc.returncode != 0:
        return "unknown"
    return stdout.decode().strip()


async def _get_commit_sha(repo_dir: Path) -> str:
    """Try to get commit SHA; return 'unknown' if not a git repo."""
    git_dir = repo_dir / ".git"
    if git_dir.exists():
        return await _rev_parse(repo_dir)
    return "unknown"


def _dir_size(
    path: Path, skip_dirs: set[str] | None = None
) -> int:
    """Compute total size of a directory tree in bytes.

    Skips symlinks (both file and directory) that resolve outside the
    root to prevent directory traversal attacks.
    """
    skips = skip_dirs or set()
    resolved_root = path.resolve()
    total = 0
    for f in path.rglob("*"):
        if skips and any(part in skips for part in f.parts):
            continue
        if f.is_symlink():
            resolved = f.resolve()
            if not resolved.is_relative_to(resolved_root):
                continue
        if f.is_file() and not f.is_symlink():
            with contextlib.suppress(OSError):
                total += f.stat().st_size
    return total
