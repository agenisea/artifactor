"""Chunk source files into semantic code segments using tree-sitter."""

from __future__ import annotations

import importlib
from pathlib import Path

import pathspec
import tree_sitter

from artifactor.config import EXTENSION_MAP, GRAMMAR_MODULES, Settings
from artifactor.constants import estimate_tokens
from artifactor.ingestion import is_binary
from artifactor.ingestion.schemas import (
    ChunkedFiles,
    CodeChunk,
    LanguageMap,
    RepoPath,
)

# Top-level node types that become individual chunks, per language.
_CHUNK_NODE_TYPES: dict[str, set[str]] = {
    "python": {
        "function_definition",
        "class_definition",
        "decorated_definition",
    },
    "javascript": {
        "function_declaration",
        "class_declaration",
        "export_statement",
        "lexical_declaration",
    },
    "typescript": {
        "function_declaration",
        "class_declaration",
        "export_statement",
        "lexical_declaration",
        "interface_declaration",
        "type_alias_declaration",
    },
    "java": {
        "class_declaration",
        "interface_declaration",
        "method_declaration",
        "enum_declaration",
    },
    "go": {
        "function_declaration",
        "method_declaration",
        "type_declaration",
    },
    "rust": {
        "function_item",
        "impl_item",
        "struct_item",
        "enum_item",
        "trait_item",
    },
    "c": {
        "function_definition",
        "struct_specifier",
        "enum_specifier",
    },
    "cpp": {
        "function_definition",
        "class_specifier",
        "struct_specifier",
        "namespace_definition",
    },
}


def chunk_code(
    repo_path: RepoPath,
    language_map: LanguageMap,
    settings: Settings | object | None = None,
) -> ChunkedFiles:
    """Chunk all source files in the repo.

    * For languages with an available grammar: parse with tree-sitter and
      extract top-level declarations as individual chunks.
    * For languages without a grammar: fall back to line-based chunking.
    * Respects ``skip_directories`` and ``.gitignore`` patterns.
    """
    if settings is None:
        settings = Settings()
    cfg = settings if isinstance(settings, Settings) else Settings()
    skip_dirs = set(cfg.skip_directories)

    # Build set of languages that have grammars
    grammar_langs: set[str] = set()
    for li in language_map.languages:
        if li.grammar_available:
            grammar_langs.add(li.name)

    root = Path(repo_path.path)
    gitignore_patterns = _load_gitignore(root)

    all_chunks: list[CodeChunk] = []
    total_files = 0
    total_lines = 0

    for file_path in _walk_source_files(root, skip_dirs, gitignore_patterns):
        ext = file_path.suffix.lower()
        lang = EXTENSION_MAP.get(ext)
        if lang is None:
            continue

        # Skip binary files
        if is_binary(file_path):
            continue

        source = _read_file(file_path)
        if source is None:
            continue

        lines = source.count("\n") + (1 if source and not source.endswith("\n") else 0)
        total_files += 1
        total_lines += lines

        rel_path = file_path.relative_to(root)

        if lang in grammar_langs:
            chunks = _semantic_chunk(
                source, lang, rel_path, cfg.max_chunk_size_tokens
            )
        else:
            chunks = _line_chunk(
                source,
                lang,
                rel_path,
                cfg.max_chunk_size_tokens,
                cfg.chunk_overlap_lines,
            )

        # Merge tiny chunks
        chunks = _merge_small_chunks(chunks, cfg.min_chunk_size_lines)
        all_chunks.extend(chunks)

    return ChunkedFiles(
        chunks=all_chunks, total_files=total_files, total_lines=total_lines
    )


# ---------------------------------------------------------------------------
# Semantic chunking (tree-sitter)
# ---------------------------------------------------------------------------


def _semantic_chunk(
    source: str,
    language: str,
    rel_path: Path,
    max_tokens: int,
) -> list[CodeChunk]:
    """Parse with tree-sitter and extract top-level declarations."""
    parser = _get_parser(language)
    if parser is None:
        return _line_chunk(source, language, rel_path, max_tokens, 50)

    tree = parser.parse(source.encode("utf-8"))
    root = tree.root_node
    node_types = _CHUNK_NODE_TYPES.get(language, set())

    chunks: list[CodeChunk] = []
    source_lines = source.split("\n")

    # Collect preamble: lines before the first declaration (imports, assignments)
    first_decl_line: int | None = None
    for child in root.children:
        if child.type in node_types:
            first_decl_line = child.start_point[0]
            break

    if first_decl_line and first_decl_line > 0:
        preamble = "\n".join(source_lines[:first_decl_line])
        if preamble.strip():
            chunks.append(
                CodeChunk(
                    file_path=rel_path,
                    language=language,
                    chunk_type="block",
                    start_line=1,
                    end_line=first_decl_line,
                    content=preamble,
                    symbol_name=None,
                )
            )

    for child in root.children:
        if child.type in node_types:
            start = child.start_point[0]  # 0-indexed line
            end = child.end_point[0]
            content = "\n".join(source_lines[start : end + 1])
            symbol = _extract_symbol_name(child)

            # Split oversized chunks at statement boundaries
            if estimate_tokens(content) > max_tokens:
                sub = _split_large_chunk(
                    source_lines, start, end, language, rel_path, max_tokens
                )
                chunks.extend(sub)
            else:
                chunks.append(
                    CodeChunk(
                        file_path=rel_path,
                        language=language,
                        chunk_type=_node_type_to_chunk_type(child.type),
                        start_line=start + 1,  # 1-indexed
                        end_line=end + 1,
                        content=content,
                        symbol_name=symbol,
                    )
                )

    # If no chunks extracted (e.g. script with no declarations), chunk entire file
    if not chunks and source.strip():
        chunks.append(
            CodeChunk(
                file_path=rel_path,
                language=language,
                chunk_type="block",
                start_line=1,
                end_line=len(source_lines),
                content=source,
                symbol_name=None,
            )
        )

    return chunks


def _extract_symbol_name(node: tree_sitter.Node) -> str | None:
    """Extract the name identifier from a declaration node."""
    # decorated_definition wraps the actual def/class
    if node.type == "decorated_definition":
        for child in node.children:
            if child.type in (
                "function_definition",
                "class_definition",
            ):
                return _extract_symbol_name(child)

    # export_statement wraps declarations in JS/TS
    if node.type == "export_statement":
        for child in node.children:
            name = _extract_symbol_name(child)
            if name:
                return name

    for child in node.children:
        if child.type in ("identifier", "name", "type_identifier"):
            return child.text.decode("utf-8") if child.text else None

    return None


def _node_type_to_chunk_type(node_type: str) -> str:
    """Map a tree-sitter node type to a human-readable chunk type."""
    if "class" in node_type or "struct" in node_type:
        return "class"
    if "function" in node_type or "method" in node_type:
        return "function"
    if "interface" in node_type or "trait" in node_type:
        return "interface"
    if "impl" in node_type:
        return "class"
    if "enum" in node_type:
        return "class"
    if "namespace" in node_type:
        return "block"
    return "block"


# ---------------------------------------------------------------------------
# Line-based fallback chunking
# ---------------------------------------------------------------------------


def _line_chunk(
    source: str,
    language: str,
    rel_path: Path,
    max_tokens: int,
    overlap: int,
) -> list[CodeChunk]:
    """Fall back to fixed-size line-based chunking with overlap."""
    lines = source.split("\n")
    # Convert max_tokens to approximate line count (~4 chars/token, ~80 chars/line)
    max_lines = max(50, max_tokens // 20)
    chunks: list[CodeChunk] = []
    start = 0

    while start < len(lines):
        end = min(start + max_lines, len(lines))
        content = "\n".join(lines[start:end])

        chunks.append(
            CodeChunk(
                file_path=rel_path,
                language=language,
                chunk_type="block",
                start_line=start + 1,
                end_line=end,
                content=content,
                symbol_name=None,
            )
        )

        if end >= len(lines):
            break
        start = end - overlap

    return chunks


def _split_large_chunk(
    source_lines: list[str],
    start: int,
    end: int,
    language: str,
    rel_path: Path,
    max_tokens: int,
) -> list[CodeChunk]:
    """Split an oversized declaration into sub-chunks."""
    max_lines = max(50, max_tokens // 20)
    chunks: list[CodeChunk] = []
    pos = start

    while pos <= end:
        chunk_end = min(pos + max_lines, end + 1)
        content = "\n".join(source_lines[pos:chunk_end])
        chunks.append(
            CodeChunk(
                file_path=rel_path,
                language=language,
                chunk_type="block",
                start_line=pos + 1,
                end_line=chunk_end,
                content=content,
                symbol_name=None,
            )
        )
        if chunk_end > end:
            break
        pos = chunk_end

    return chunks


def _merge_small_chunks(
    chunks: list[CodeChunk], min_lines: int
) -> list[CodeChunk]:
    """Merge adjacent chunks that are below the minimum line threshold."""
    if not chunks:
        return chunks

    merged: list[CodeChunk] = [chunks[0]]
    for chunk in chunks[1:]:
        prev = merged[-1]
        prev_lines = prev.end_line - prev.start_line + 1
        cur_lines = chunk.end_line - chunk.start_line + 1

        if (
            prev_lines < min_lines
            and cur_lines < min_lines
            and prev.file_path == chunk.file_path
        ):
            # Merge into previous
            merged[-1] = CodeChunk(
                file_path=prev.file_path,
                language=prev.language,
                chunk_type="block",
                start_line=prev.start_line,
                end_line=chunk.end_line,
                content=prev.content + "\n" + chunk.content,
                symbol_name=prev.symbol_name,
            )
        else:
            merged.append(chunk)

    return merged


# ---------------------------------------------------------------------------
# Parser cache and helpers
# ---------------------------------------------------------------------------

_parser_cache: dict[str, tree_sitter.Parser] = {}


def _get_parser(language: str) -> tree_sitter.Parser | None:
    """Get or create a cached tree-sitter parser for the language."""
    if language in _parser_cache:
        return _parser_cache[language]

    module_name = GRAMMAR_MODULES.get(language)
    if module_name is None:
        return None

    try:
        mod = importlib.import_module(module_name)
        capsule: object = mod.language()
        lang = tree_sitter.Language(capsule)
        parser = tree_sitter.Parser(lang)
        _parser_cache[language] = parser
        return parser
    except (ImportError, AttributeError):
        return None



def _read_file(path: Path) -> str | None:
    """Read a file as UTF-8 text, returning None on failure."""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return None


def _walk_source_files(
    root: Path,
    skip_dirs: set[str],
    gitignore_patterns: pathspec.PathSpec,
) -> list[Path]:
    """Walk the file tree, respecting skip dirs and gitignore patterns.

    Symlinks that resolve outside the repo root are skipped to prevent
    directory traversal attacks.
    """
    resolved_root = root.resolve()
    return _walk_source_files_inner(
        root, root, skip_dirs, gitignore_patterns, resolved_root
    )


def _walk_source_files_inner(
    current: Path,
    root: Path,
    skip_dirs: set[str],
    gitignore_patterns: pathspec.PathSpec,
    resolved_root: Path,
) -> list[Path]:
    """Recursive walk helper with symlink protection."""
    files: list[Path] = []
    for item in sorted(current.iterdir()):
        if item.is_symlink():
            resolved = item.resolve()
            if not resolved.is_relative_to(resolved_root):
                continue
        rel = str(item.relative_to(root))
        if item.is_dir():
            if item.name.startswith(".") or item.name in skip_dirs:
                continue
            if gitignore_patterns.match_file(rel + "/"):
                continue
            files.extend(
                _walk_source_files_inner(
                    item, root, skip_dirs, gitignore_patterns,
                    resolved_root,
                )
            )
        elif item.is_file():
            if not gitignore_patterns.match_file(rel):
                files.append(item)
    return files


def _load_gitignore(root: Path) -> pathspec.PathSpec:
    """Load .gitignore patterns using pathspec."""
    gitignore = root / ".gitignore"
    if not gitignore.exists():
        return pathspec.PathSpec.from_lines(
            "gitignore", []
        )
    try:
        with open(gitignore, encoding="utf-8") as f:
            return pathspec.PathSpec.from_lines(
                "gitignore", f
            )
    except OSError:
        return pathspec.PathSpec.from_lines(
            "gitignore", []
        )
