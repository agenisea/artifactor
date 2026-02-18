"""Orchestrate all static analysis modules."""

from __future__ import annotations

import asyncio
import logging

from artifactor.analysis.static.api_discovery import discover_endpoints
from artifactor.analysis.static.ast_parser import parse_asts
from artifactor.analysis.static.call_graph import build_call_graph
from artifactor.analysis.static.dependency_graph import extract_imports
from artifactor.analysis.static.schema_extractor import extract_schemas
from artifactor.analysis.static.schemas import (
    APIEndpoints,
    ASTForest,
    CallGraph,
    DependencyGraph,
    SchemaMap,
    StaticAnalysisResult,
)
from artifactor.ingestion.schemas import ChunkedFiles, LanguageMap, RepoPath

logger = logging.getLogger(__name__)


async def run_static_analysis(
    repo_path: RepoPath,
    chunked_files: ChunkedFiles,
    language_map: LanguageMap,
) -> StaticAnalysisResult:
    """Run all five static analysis modules in parallel.

    AST parsing runs first (call_graph, schema_extractor, and
    api_discovery depend on its output). The remaining 4 modules
    run in parallel via asyncio.gather() with to_thread() wrappers
    for CPU-bound tree-sitter work.

    Each module has independent error recovery — if one fails,
    its result is empty and the remaining modules still complete.
    """
    # 1. Parse ASTs (must run first — others depend on it)
    try:
        ast_forest = await asyncio.to_thread(
            parse_asts, chunked_files, language_map
        )
    except Exception:  # noqa: BLE001
        logger.warning("AST parsing failed", exc_info=True)
        ast_forest = ASTForest()

    # 2. Remaining 4 modules in parallel
    async def _call_graph() -> CallGraph:
        try:
            return await asyncio.to_thread(
                build_call_graph,
                ast_forest,
                chunked_files,
                language_map,
            )
        except Exception:  # noqa: BLE001
            logger.warning(
                "Call graph failed", exc_info=True
            )
            return CallGraph()

    async def _dependency_graph() -> DependencyGraph:
        try:
            return await asyncio.to_thread(
                extract_imports,
                chunked_files,
                language_map,
            )
        except Exception:  # noqa: BLE001
            logger.warning(
                "Dependency graph failed", exc_info=True
            )
            return DependencyGraph()

    async def _schema_map() -> SchemaMap:
        try:
            return await asyncio.to_thread(
                extract_schemas,
                ast_forest,
                chunked_files,
                language_map,
            )
        except Exception:  # noqa: BLE001
            logger.warning(
                "Schema extraction failed", exc_info=True
            )
            return SchemaMap()

    async def _api_endpoints() -> APIEndpoints:
        try:
            return await asyncio.to_thread(
                discover_endpoints,
                ast_forest,
                chunked_files,
                language_map,
            )
        except Exception:  # noqa: BLE001
            logger.warning(
                "API discovery failed", exc_info=True
            )
            return APIEndpoints()

    call_graph, dependency_graph, schema_map, api_endpoints = (
        await asyncio.gather(
            _call_graph(),
            _dependency_graph(),
            _schema_map(),
            _api_endpoints(),
        )
    )

    return StaticAnalysisResult(
        ast_forest=ast_forest,
        call_graph=call_graph,
        dependency_graph=dependency_graph,
        schema_map=schema_map,
        api_endpoints=api_endpoints,
    )
