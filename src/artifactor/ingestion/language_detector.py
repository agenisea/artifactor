"""Detect programming languages in a repository via file extensions."""

from __future__ import annotations

import importlib
from collections import defaultdict
from pathlib import Path

import pathspec

from artifactor.config import EXTENSION_MAP, GRAMMAR_MODULES, Settings
from artifactor.ingestion import is_binary
from artifactor.ingestion.schemas import LanguageInfo, LanguageMap, RepoPath


def detect_languages(
    repo_path: RepoPath,
    settings: Settings | object | None = None,
) -> LanguageMap:
    """Walk the repo tree and return a :class:`LanguageMap`.

    * Skips hidden directories (``.git``, ``.svn``, ``.hg``) and
      directories listed in ``settings.skip_directories``.
    * Skips binary files (null byte in first 8192 bytes).
    * Maps file extensions to language names via :data:`EXTENSION_MAP`.
    * Checks grammar availability via dynamic import.
    """
    if settings is None:
        settings = Settings()
    cfg = settings if isinstance(settings, Settings) else Settings()
    skip_dirs = set(cfg.skip_directories)

    # Accumulate per-language stats
    lang_files: dict[str, int] = defaultdict(int)
    lang_lines: dict[str, int] = defaultdict(int)
    lang_exts: dict[str, set[str]] = defaultdict(set)

    root = Path(repo_path.path)
    gitignore_spec = _load_gitignore(root)
    for file_path in _walk_files(root, skip_dirs, gitignore_spec):
        ext = file_path.suffix.lower()
        lang = EXTENSION_MAP.get(ext)
        if lang is None:
            lang = "unknown"

        if is_binary(file_path):
            continue

        lines = _count_lines(file_path)
        lang_files[lang] += 1
        lang_lines[lang] += lines
        lang_exts[lang].add(ext)

    # Build LanguageInfo list sorted by line count descending
    languages: list[LanguageInfo] = []
    for name in sorted(lang_files, key=lambda n: lang_lines[n], reverse=True):
        grammar = _check_grammar(name)
        languages.append(
            LanguageInfo(
                name=name,
                file_count=lang_files[name],
                line_count=lang_lines[name],
                grammar_available=grammar,
                extensions=sorted(lang_exts[name]),
            )
        )

    primary = languages[0].name if languages else None
    return LanguageMap(languages=languages, primary_language=primary)


def _walk_files(
    root: Path,
    skip_dirs: set[str],
    gitignore_spec: pathspec.PathSpec,
) -> list[Path]:
    """Yield all regular files, skipping hidden and excluded directories.

    Symlinks (both directory and file) that resolve outside the repo root
    are skipped to prevent directory traversal attacks.
    """
    resolved_root = root.resolve()
    return _walk_files_inner(
        root, root, skip_dirs, gitignore_spec, resolved_root
    )


def _walk_files_inner(
    current: Path,
    root: Path,
    skip_dirs: set[str],
    gitignore_spec: pathspec.PathSpec,
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
            # Skip hidden dirs and explicitly excluded dirs
            if item.name.startswith(".") or item.name in skip_dirs:
                continue
            if gitignore_spec.match_file(rel + "/"):
                continue
            files.extend(
                _walk_files_inner(
                    item, root, skip_dirs, gitignore_spec,
                    resolved_root,
                )
            )
        elif item.is_file():
            if not gitignore_spec.match_file(rel):
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




def _count_lines(path: Path) -> int:
    """Count lines in a text file. Returns 0 on read errors."""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return sum(1 for _ in f)
    except OSError:
        return 0


def _check_grammar(language: str) -> bool:
    """Check whether a tree-sitter grammar is importable for the language."""
    module_name = GRAMMAR_MODULES.get(language)
    if module_name is None:
        return False
    try:
        importlib.import_module(module_name)
        return True
    except ImportError:
        return False
