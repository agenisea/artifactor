"""MCP tool definitions: 10 tools mirroring the agent layer."""

# pyright: reportUnusedFunction=false
# All functions are registered via @mcp.tool decorator

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastmcp import FastMCP

from artifactor.constants import CALL_GRAPH_MAX_DEPTH, CALL_GRAPH_MIN_DEPTH
from artifactor.repositories.document_repo import (
    SqlDocumentRepository,
)
from artifactor.repositories.entity_repo import (
    SqlEntityRepository,
)
from artifactor.repositories.relationship_repo import (
    SqlRelationshipRepository,
)


def register_tools(mcp: FastMCP) -> None:
    """Register all 10 MCP tools."""

    @mcp.tool()
    async def query_codebase(
        question: str,
        project_id: str = "",
    ) -> str:
        """Search the Intelligence Model for answers.

        Returns an answer with source citations.
        """
        pid = _resolve_project_id(project_id)
        from artifactor.chat.rag_pipeline import (
            retrieve_context,
        )

        async with _session_repos() as (
            entity_repo,
            document_repo,
        ):
            ctx = await retrieve_context(
                question,
                pid,
                entity_repo,
                document_repo,
            )
        if (
            not ctx.formatted
            or ctx.formatted == "No context found."
        ):
            return (
                "No relevant context found for: "
                f"{question}"
            )
        return ctx.formatted

    @mcp.tool()
    async def get_specification(
        section: str,
        project_id: str = "",
    ) -> str:
        """Retrieve a documentation section by name.

        Valid sections: executive_overview, features,
        personas, user_stories, security_requirements,
        system_overview, data_models, interfaces,
        ui_specs, api_specs, integrations, tech_stories,
        security_considerations.
        """
        pid = _resolve_project_id(project_id)
        async with _session_repos() as (
            _,
            document_repo,
        ):
            doc = await document_repo.get_section(
                pid, section
            )
        if doc is None:
            return (
                f"Section '{section}' not yet generated."
            )
        return doc.content

    @mcp.tool()
    async def list_features(
        project_id: str = "",
    ) -> str:
        """List all discovered features with code mappings."""
        pid = _resolve_project_id(project_id)
        async with _session_repos() as (
            _,
            document_repo,
        ):
            doc = await document_repo.get_section(
                pid, "features"
            )
        if doc is None:
            return "Feature analysis not yet complete."
        return doc.content

    @mcp.tool()
    async def get_data_model(
        entity: str = "",
        project_id: str = "",
    ) -> str:
        """Get entity attributes, types, and relationships."""
        pid = _resolve_project_id(project_id)
        async with _session_repos() as (
            entity_repo,
            document_repo,
        ):
            if entity:
                entities = await entity_repo.search(
                    pid, entity, entity_type="table"
                )
                if not entities:
                    return f"Entity '{entity}' not found."
                parts = [
                    f"{e.name} ({e.entity_type}) at "
                    f"{e.file_path}:{e.start_line}"
                    for e in entities
                ]
                return "\n".join(parts)
            doc = await document_repo.get_section(
                pid, "data_models"
            )
        if doc is None:
            return "Data model analysis not yet complete."
        return doc.content

    @mcp.tool()
    async def explain_symbol(
        file_path: str,
        symbol_name: str = "",
        project_id: str = "",
    ) -> str:
        """Explain purpose, callers, and callees for a symbol."""
        pid = _resolve_project_id(project_id)
        async with _session_repos() as (
            entity_repo,
            _,
        ):
            entities = await entity_repo.get_by_path(
                pid, file_path
            )
        if not entities:
            return f"No entities found at '{file_path}'."
        if symbol_name:
            entities = [
                e
                for e in entities
                if e.name == symbol_name
            ]
            if not entities:
                return (
                    f"Symbol '{symbol_name}' not found "
                    f"in '{file_path}'."
                )
        async with _session_relationship_repo() as rel_repo:
            callers = await rel_repo.get_callers(
                pid, file_path, symbol_name, depth=2
            )
            callees = await rel_repo.get_callees(
                pid, file_path, symbol_name, depth=2
            )
        parts = [f"Entities at {file_path}:"]
        for e in entities:
            parts.append(
                f"  - {e.name} ({e.entity_type}) "
                f"lines {e.start_line}-{e.end_line}"
            )
        if callers:
            parts.append("Callers:")
            for c in callers:
                parts.append(
                    f"  - {c.source_file}"
                    f":{c.source_symbol}"
                )
        if callees:
            parts.append("Callees:")
            for c in callees:
                parts.append(
                    f"  - {c.target_file}"
                    f":{c.target_symbol}"
                )
        return "\n".join(parts)

    @mcp.tool()
    async def get_call_graph(
        file_path: str,
        symbol_name: str,
        direction: str = "both",
        depth: int = 2,
        project_id: str = "",
    ) -> str:
        """Get call graph for a function or method.

        direction: 'callers', 'callees', or 'both'.
        depth: traversal depth (1-5).
        """
        pid = _resolve_project_id(project_id)
        depth = min(max(depth, CALL_GRAPH_MIN_DEPTH), CALL_GRAPH_MAX_DEPTH)
        parts: list[str] = []
        async with _session_relationship_repo() as rel_repo:
            if direction in ("callers", "both"):
                callers = await rel_repo.get_callers(
                    pid,
                    file_path,
                    symbol_name,
                    depth=depth,
                )
                parts.append(
                    f"Callers of {symbol_name} "
                    f"(depth={depth}):"
                )
                for c in callers:
                    parts.append(
                        f"  {c.source_file}"
                        f":{c.source_symbol}"
                        f" -> {c.target_symbol}"
                    )
            if direction in ("callees", "both"):
                callees = await rel_repo.get_callees(
                    pid,
                    file_path,
                    symbol_name,
                    depth=depth,
                )
                parts.append(
                    f"Callees of {symbol_name} "
                    f"(depth={depth}):"
                )
                for c in callees:
                    parts.append(
                        f"  {c.source_symbol} -> "
                        f"{c.target_file}:{c.target_symbol}"
                    )
        if not parts:
            return (
                f"No call graph data for "
                f"{file_path}:{symbol_name}."
            )
        return "\n".join(parts)

    @mcp.tool()
    async def get_user_stories(
        epic: str = "",
        persona: str = "",
        project_id: str = "",
    ) -> str:
        """Get user stories with acceptance criteria."""
        pid = _resolve_project_id(project_id)
        async with _session_repos() as (
            _,
            document_repo,
        ):
            doc = await document_repo.get_section(
                pid, "user_stories"
            )
        if doc is None:
            return "User stories not yet generated."
        content = doc.content
        if epic:
            content = (
                f"[Filtered by epic: {epic}]\n{content}"
            )
        if persona:
            content = (
                f"[Filtered by persona: "
                f"{persona}]\n{content}"
            )
        return content

    @mcp.tool()
    async def get_api_endpoints(
        path_filter: str = "",
        method: str = "",
        project_id: str = "",
    ) -> str:
        """Get discovered API endpoints."""
        pid = _resolve_project_id(project_id)
        async with _session_repos() as (
            entity_repo,
            _,
        ):
            entities = await entity_repo.search(
                pid,
                query=path_filter,
                entity_type="endpoint",
            )
        if method:
            entities = [
                e
                for e in entities
                if method.upper()
                in (e.signature or "").upper()
            ]
        if not entities:
            return "No API endpoints found."
        parts = ["Discovered API endpoints:"]
        for e in entities:
            sig = e.signature or "UNKNOWN"
            parts.append(
                f"  {sig} {e.name} "
                f"[{e.file_path}:{e.start_line}]"
            )
        return "\n".join(parts)

    @mcp.tool()
    async def search_code_entities(
        query: str,
        entity_type: str = "",
        project_id: str = "",
    ) -> str:
        """Search code entities by name or keyword."""
        pid = _resolve_project_id(project_id)
        async with _session_repos() as (
            entity_repo,
            _,
        ):
            entities = await entity_repo.search(
                pid,
                query,
                entity_type=entity_type or None,
            )
        if not entities:
            return (
                f"No entities found matching '{query}'."
            )
        parts = [f"Found {len(entities)} entities:"]
        for e in entities:
            parts.append(
                f"  {e.name} ({e.entity_type}) at "
                f"{e.file_path}:{e.start_line}"
            )
        return "\n".join(parts)

    @mcp.tool()
    async def get_security_findings(
        severity: str = "",
        category: str = "",
        project_id: str = "",
    ) -> str:
        """Get security findings with affected files."""
        pid = _resolve_project_id(project_id)
        async with _session_repos() as (
            _,
            document_repo,
        ):
            doc = await document_repo.get_section(
                pid, "security_considerations"
            )
        if doc is None:
            return "Security analysis not yet complete."
        content = doc.content
        if severity:
            content = (
                f"[Filtered by severity: "
                f"{severity}]\n{content}"
            )
        if category:
            content = (
                f"[Filtered by category: "
                f"{category}]\n{content}"
            )
        return content


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


@asynccontextmanager
async def _session_repos() -> AsyncIterator[
    tuple[SqlEntityRepository, SqlDocumentRepository]
]:
    """Yield repos with proper session lifecycle."""
    from artifactor.mcp.server import (
        get_session_factory,
    )

    factory = get_session_factory()
    async with factory() as session:
        yield (
            SqlEntityRepository(session),
            SqlDocumentRepository(session),
        )


@asynccontextmanager
async def _session_relationship_repo() -> (
    AsyncIterator[SqlRelationshipRepository]
):
    """Yield relationship repo with proper session lifecycle."""
    from artifactor.mcp.server import (
        get_session_factory,
    )

    factory = get_session_factory()
    async with factory() as session:
        yield SqlRelationshipRepository(session)
