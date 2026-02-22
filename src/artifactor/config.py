"""Environment-based configuration and application constants."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated, Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Reads from .env file and environment variables."""

    # LLM Provider
    anthropic_api_key: str = ""
    openai_api_key: str = ""

    # Model chain (first = primary, rest = fallbacks tried in order)
    litellm_model_chain: Annotated[list[str], NoDecode] = [
        "openai/gpt-4.1-mini",
        "openai/gpt-4.0-mini",
    ]
    llm_max_concurrency: int = 2
    llm_timeout_seconds: int = 60

    # Database
    database_url: str = "sqlite:///data/artifactor.db"

    # Directories
    data_dir: Path = Path("data")
    log_dir: Path = Path("logs")
    static_dir: Path = Path("static")

    # Logging
    log_level: str = "INFO"
    debug_mode: bool = False

    # Analysis
    max_repo_size_bytes: int = 2_147_483_648  # 2GB
    analysis_timeout_seconds: int = 900
    analysis_max_concurrency: int = 5

    # API
    api_key: str = ""
    cors_origins: str = "http://localhost:3000"
    browse_root: str = ""  # empty = Path.home(); set for production

    # LanceDB + Embeddings
    lancedb_uri: str = "data/lancedb"
    litellm_embedding_model: str = "openai/text-embedding-3-small"
    rag_vector_top_k: int = 10

    # Observability (optional)
    langsmith_api_key: str = ""
    langsmith_project: str = "artifactor"
    otel_enabled: bool = False
    trace_enabled: bool = True

    # Ingestion
    max_chunk_size_tokens: int = 6000
    min_chunk_size_lines: int = 10
    chunk_overlap_lines: int = 50
    skip_directories: list[str] = [
        "node_modules",
        "vendor",
        ".venv",
        "__pycache__",
        "build",
        "dist",
        "target",
        ".git",
        ".svn",
        ".hg",
        ".next",
    ]

    @field_validator("litellm_model_chain", mode="before")
    @classmethod
    def _parse_chain(cls, v: Any) -> Any:
        """Accept comma-separated string or JSON array."""
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v

    @field_validator("litellm_model_chain")
    @classmethod
    def _validate_chain(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError(
                "litellm_model_chain must contain at least one model"
            )
        seen: set[str] = set()
        dupes: list[str] = []
        for m in v:
            if m in seen:
                dupes.append(m)
            seen.add(m)
        if dupes:
            logger.warning(
                "Duplicate models in LITELLM_MODEL_CHAIN: %s",
                ", ".join(dupes),
            )
        return v

    @property
    def pydantic_ai_models(self) -> list[str]:
        """Full model chain in pydantic-ai provider:model format."""
        return [m.replace("/", ":", 1) for m in self.litellm_model_chain]

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "env_prefix": "",
        "extra": "ignore",
    }


# Agent identifiers
AGENT_IDS = {
    "INGESTION": "ingestion_agent",
    "STATIC_ANALYSIS": "static_analysis_agent",
    "LLM_ANALYSIS": "llm_analysis_agent",
    "QUALITY": "quality_agent",
    "SECTION_GENERATOR": "section_generator_agent",
    "CHAT": "chat_agent",
}

# Timeout budgets (seconds)
TIMEOUTS = {
    "ingestion_agent": 120,
    "static_analysis_agent": 180,
    "llm_analysis_agent": 300,
    "quality_agent": 120,
    "section_generator_agent": 60,
    "chat_agent": 120,
    "pipeline_total": 900,
}

# Section generator names
# File extension → language name mapping
EXTENSION_MAP: dict[str, str] = {
    # Python
    ".py": "python",
    ".pyi": "python",
    ".pyw": "python",
    # JavaScript
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".jsx": "javascript",
    # TypeScript
    ".ts": "typescript",
    ".tsx": "typescript",
    ".mts": "typescript",
    ".cts": "typescript",
    # Java
    ".java": "java",
    # Go
    ".go": "go",
    # Rust
    ".rs": "rust",
    # C
    ".c": "c",
    ".h": "c",
    # C++
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".hpp": "cpp",
    ".hxx": "cpp",
    ".hh": "cpp",
    # C#
    ".cs": "c_sharp",
    # Ruby
    ".rb": "ruby",
    ".rake": "ruby",
    # PHP
    ".php": "php",
    # Swift
    ".swift": "swift",
    # Kotlin
    ".kt": "kotlin",
    ".kts": "kotlin",
    # Scala
    ".scala": "scala",
    # Lua
    ".lua": "lua",
    # Shell
    ".sh": "bash",
    ".bash": "bash",
    ".zsh": "bash",
    # HTML
    ".html": "html",
    ".htm": "html",
    # CSS
    ".css": "css",
    # JSON
    ".json": "json",
    # YAML
    ".yml": "yaml",
    ".yaml": "yaml",
    # TOML
    ".toml": "toml",
    # Markdown
    ".md": "markdown",
    ".mdx": "markdown",
    # SQL
    ".sql": "sql",
    # Elixir
    ".ex": "elixir",
    ".exs": "elixir",
    # Haskell
    ".hs": "haskell",
    # OCaml
    ".ml": "ocaml",
    ".mli": "ocaml",
    # R
    ".r": "r",
    ".R": "r",
    # Dart
    ".dart": "dart",
    # Zig
    ".zig": "zig",
}

# Grammar module name → import path for tree-sitter grammars
GRAMMAR_MODULES: dict[str, str] = {
    "python": "tree_sitter_python",
    "javascript": "tree_sitter_javascript",
    "typescript": "tree_sitter_typescript",
    "java": "tree_sitter_java",
    "go": "tree_sitter_go",
    "rust": "tree_sitter_rust",
    "c": "tree_sitter_c",
    "cpp": "tree_sitter_cpp",
}

SECTION_TITLES: dict[str, str] = {
    "executive_overview": "Executive Overview",
    "features": "Main Application Features",
    "personas": "User Personas",
    "user_stories": "User Stories",
    "security_requirements": "Security Requirements",
    "system_overview": "System Overview",
    "data_models": "Data Models",
    "interfaces": "Interface Specifications",
    "ui_specs": "UI Specifications",
    "api_specs": "API Specifications",
    "integrations": "Integration Points",
    "tech_stories": "Technical User Stories",
    "security_considerations": "Security Considerations",
}


def create_app_engine(
    url: str, *, echo: bool = False
) -> AsyncEngine:
    """Create async SQLite engine with WAL journal mode.

    Handles URL conversion (sqlite:/// → sqlite+aiosqlite:///)
    and sets WAL mode via a pool-connect event listener so it
    fires once per raw DBAPI connection, not per ORM session.
    """
    if url.startswith("sqlite:///"):
        db_url = "sqlite+aiosqlite:///" + url[len("sqlite:///"):]
    else:
        db_url = url
    engine = create_async_engine(db_url, echo=echo)

    @event.listens_for(engine.sync_engine, "connect")
    def _set_wal_mode(
        dbapi_conn: object,
        _connection_record: object,
    ) -> None:
        cursor = dbapi_conn.cursor()  # type: ignore[union-attr]
        cursor.execute("PRAGMA journal_mode=WAL")  # pyright: ignore[reportUnknownMemberType]
        cursor.close()  # pyright: ignore[reportUnknownMemberType]

    return engine
