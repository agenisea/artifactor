"""Pydantic models for the ingestion data flow."""

from pathlib import Path

from pydantic import BaseModel, Field


class RepoSource(BaseModel):
    """Input to git_connector — describes where to find the repository."""

    local_path: Path
    branch: str = "main"


class RepoPath(BaseModel):
    """Output of git_connector — a local path with commit metadata."""

    path: Path
    commit_sha: str
    branch: str


class LanguageInfo(BaseModel):
    """Per-language statistics detected in a repository."""

    name: str
    file_count: int = 0
    line_count: int = 0
    grammar_available: bool = False
    extensions: list[str] = Field(default_factory=list)


class LanguageMap(BaseModel):
    """Output of language_detector — all languages found in the repo."""

    languages: list[LanguageInfo] = Field(default_factory=lambda: list[LanguageInfo]())
    primary_language: str | None = None


class CodeChunk(BaseModel):
    """A single semantic chunk of source code."""

    file_path: Path
    language: str
    chunk_type: str  # "function", "class", "method", "interface", "block"
    start_line: int
    end_line: int
    content: str
    symbol_name: str | None = None


class ChunkedFiles(BaseModel):
    """Output of chunker — all chunks from the repository."""

    chunks: list[CodeChunk] = Field(default_factory=lambda: list[CodeChunk]())
    total_files: int = 0
    total_lines: int = 0
