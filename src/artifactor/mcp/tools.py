"""MCP tool definitions: 10 tools delegating to shared tool_logic.

Each tool is a thin wrapper that resolves project_id, opens a
unified session via SessionRepos, and delegates to do_*() from
tool_logic.py. Business logic lives in tool_logic.py (ISP/DRY).
"""

# pyright: reportUnusedFunction=false
# All functions are registered via @mcp.tool decorator

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import NamedTuple

from fastmcp import FastMCP

from artifactor.agent.tool_logic import (
    do_explain_symbol,
    do_get_api_endpoints,
    do_get_call_graph,
    do_get_data_model,
    do_get_security_findings,
    do_get_specification,
    do_get_user_stories,
    do_list_features,
    do_query_codebase,
    do_search_code_entities,
)
from artifactor.config import Settings
from artifactor.constants import (
    CALL_GRAPH_DEFAULT_DEPTH,
    CALL_GRAPH_DEFAULT_DIRECTION,
)
from artifactor.repositories.document_repo import (
    SqlDocumentRepository,
)
from artifactor.repositories.entity_repo import (
    SqlEntityRepository,
)
from artifactor.repositories.relationship_repo import (
    SqlRelationshipRepository,
)

# ── Cached Settings ──────────────────────────────────


@lru_cache(maxsize=1)
def _get_settings() -> Settings:
    """Cached Settings — avoids re-reading .env per call."""
    return Settings()


# ── Unified Session Context ──────────────────────────


class SessionRepos(NamedTuple):
    """All three repos from a single database session.

    Uses concrete SQL repo types (not protocols) because this
    is the infrastructure edge. The do_*() functions accept
    protocol interfaces — DIP is enforced there.
    """

    entity: SqlEntityRepository
    document: SqlDocumentRepository
    relationship: SqlRelationshipRepository


@asynccontextmanager
async def _session_repos() -> AsyncIterator[SessionRepos]:
    """Yield all three repos from a single session."""
    from artifactor.mcp.server import get_session_factory

    factory = get_session_factory()
    async with factory() as session:
        yield SessionRepos(
            entity=SqlEntityRepository(session),
            document=SqlDocumentRepository(session),
            relationship=SqlRelationshipRepository(
                session
            ),
        )


# ── Project ID Resolution ───────────────────────────


def _resolve_project_id(project_id: str) -> str:
    """Resolve project_id, falling back to default."""
    if project_id:
        return project_id
    from artifactor.mcp.server import (
        get_default_project_id,
    )

    default = get_default_project_id()
    if default:
        return default
    msg = "project_id is required"
    raise ValueError(msg)


# ── Tool Registration ───────────────────────────────


def register_tools(mcp: FastMCP) -> None:
    """Register all 10 MCP tools."""

    @mcp.tool()
    async def query_codebase(
        question: str,
        project_id: str = "",
    ) -> str:
        """Search the Intelligence Model for answers."""
        pid = _resolve_project_id(project_id)
        async with _session_repos() as repos:
            return await do_query_codebase(
                question,
                pid,
                repos.entity,
                repos.document,
                _get_settings(),
            )

    @mcp.tool()
    async def get_specification(
        section: str,
        project_id: str = "",
    ) -> str:
        """Retrieve a documentation section by name."""
        pid = _resolve_project_id(project_id)
        async with _session_repos() as repos:
            return await do_get_specification(
                section, pid, repos.document
            )

    @mcp.tool()
    async def list_features(
        project_id: str = "",
    ) -> str:
        """List all discovered features with code mappings."""
        pid = _resolve_project_id(project_id)
        async with _session_repos() as repos:
            return await do_list_features(
                pid, repos.document
            )

    @mcp.tool()
    async def get_data_model(
        entity: str = "",
        project_id: str = "",
    ) -> str:
        """Get entity attributes, types, and relationships."""
        pid = _resolve_project_id(project_id)
        async with _session_repos() as repos:
            return await do_get_data_model(
                pid,
                repos.entity,
                repos.document,
                entity,
            )

    @mcp.tool()
    async def explain_symbol(
        file_path: str,
        symbol_name: str = "",
        project_id: str = "",
    ) -> str:
        """Explain purpose, callers, and callees."""
        pid = _resolve_project_id(project_id)
        async with _session_repos() as repos:
            return await do_explain_symbol(
                file_path,
                pid,
                repos.entity,
                repos.relationship,
                symbol_name,
            )

    @mcp.tool()
    async def get_call_graph(
        file_path: str,
        symbol_name: str,
        direction: str = CALL_GRAPH_DEFAULT_DIRECTION,
        depth: int = CALL_GRAPH_DEFAULT_DEPTH,
        project_id: str = "",
    ) -> str:
        """Get call graph for a function or method."""
        pid = _resolve_project_id(project_id)
        async with _session_repos() as repos:
            return await do_get_call_graph(
                file_path,
                symbol_name,
                pid,
                repos.relationship,
                direction,
                depth,
            )

    @mcp.tool()
    async def get_user_stories(
        epic: str = "",
        persona: str = "",
        project_id: str = "",
    ) -> str:
        """Get user stories with acceptance criteria."""
        pid = _resolve_project_id(project_id)
        async with _session_repos() as repos:
            return await do_get_user_stories(
                pid, repos.document, epic, persona
            )

    @mcp.tool()
    async def get_api_endpoints(
        path_filter: str = "",
        method: str = "",
        project_id: str = "",
    ) -> str:
        """Get discovered API endpoints."""
        pid = _resolve_project_id(project_id)
        async with _session_repos() as repos:
            return await do_get_api_endpoints(
                pid,
                repos.entity,
                path_filter,
                method,
            )

    @mcp.tool()
    async def search_code_entities(
        query: str,
        entity_type: str = "",
        project_id: str = "",
    ) -> str:
        """Search code entities by name or keyword."""
        pid = _resolve_project_id(project_id)
        async with _session_repos() as repos:
            return await do_search_code_entities(
                query,
                pid,
                repos.entity,
                entity_type,
            )

    @mcp.tool()
    async def get_security_findings(
        severity: str = "",
        category: str = "",
        project_id: str = "",
    ) -> str:
        """Get security findings with affected files."""
        pid = _resolve_project_id(project_id)
        async with _session_repos() as repos:
            return await do_get_security_findings(
                pid,
                repos.document,
                severity,
                category,
            )
