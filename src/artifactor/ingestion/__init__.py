"""Code ingestion pipeline — resolve repo, detect languages, chunk."""

from pathlib import Path

from artifactor.constants import BINARY_DETECTION_BUFFER
from artifactor.ingestion.schemas import (
    ChunkedFiles,
    CodeChunk,
    LanguageInfo,
    LanguageMap,
    RepoPath,
    RepoSource,
)

__all__ = [
    "ChunkedFiles",
    "CodeChunk",
    "LanguageInfo",
    "LanguageMap",
    "RepoPath",
    "RepoSource",
    "chunk_code",
    "detect_languages",
    "is_binary",
    "resolve_local_repo",
]


def is_binary(path: Path) -> bool:
    """Return True if the file appears to be binary (null byte in first N bytes)."""
    try:
        with open(path, "rb") as f:
            chunk = f.read(BINARY_DETECTION_BUFFER)
        return b"\x00" in chunk
    except OSError:
        return True


async def resolve_local_repo(
    source: RepoSource, settings: object | None = None
) -> RepoPath:
    """Resolve a local repository path for analysis."""
    from artifactor.ingestion.git_connector import resolve_local_repo as _impl

    return await _impl(source, settings)


async def detect_languages(
    repo_path: RepoPath, settings: object | None = None
) -> LanguageMap:
    """Detect programming languages in the repository."""
    from artifactor.ingestion.language_detector import detect_languages as _impl

    return _impl(repo_path, settings)


async def chunk_code(
    repo_path: RepoPath,
    language_map: LanguageMap,
    settings: object | None = None,
) -> ChunkedFiles:
    """Chunk source files into semantic code segments."""
    from artifactor.ingestion.chunker import chunk_code as _impl

    return _impl(repo_path, language_map, settings)
