"""Agent tool registration with error handling."""

# pyright: reportUnusedFunction=false
# All functions in register_tools() are registered via @agent.tool

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any

from pydantic_ai import Agent, RunContext

from artifactor.agent.deps import AgentDeps
from artifactor.agent.schemas import AgentResponse
from artifactor.constants import CALL_GRAPH_MAX_DEPTH, CALL_GRAPH_MIN_DEPTH


def handle_tool_errors(
    fn: Callable[..., Any],
) -> Callable[..., Any]:
    """Wrap a tool function to catch exceptions and return error strings."""

    @functools.wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return await fn(*args, **kwargs)
        except Exception as exc:
            return (
                f"Tool error ({type(exc).__name__}): {exc}"
            )

    return wrapper


def register_tools(
    agent: Agent[AgentDeps, AgentResponse],
) -> None:
    """Register all 10 agent tools on the given agent instance."""

    @agent.tool
    @handle_tool_errors
    async def query_codebase(
        ctx: RunContext[AgentDeps],
        question: str,
    ) -> str:
        """Search the codebase using hybrid vector + keyword search.

        Returns relevant code entities, documentation sections,
        and semantic matches with source citations.
        """
        from artifactor.chat.rag_pipeline import (
            retrieve_context,
        )

        deps = ctx.deps
        context = await retrieve_context(
            query=question,
            project_id=deps.project_id,
            entity_repo=deps.entity_repo,
            document_repo=deps.document_repo,
        )
        if not context.formatted:
            return (
                f"No relevant results found for: "
                f"{question}"
            )
        return context.formatted

    @agent.tool
    @handle_tool_errors
    async def get_specification(
        ctx: RunContext[AgentDeps],
        section: str,
    ) -> str:
        """Retrieve a full documentation section by name.

        Valid sections: executive_overview, features, personas,
        user_stories, security_requirements, system_overview,
        data_models, interfaces, ui_specs, api_specs,
        integrations, tech_stories, security_considerations.
        """
        deps = ctx.deps
        doc = await deps.document_repo.get_section(
            deps.project_id, section
        )
        if doc is None:
            return (
                f"Section '{section}' not yet generated "
                "for this project."
            )
        return doc.content

    @agent.tool
    @handle_tool_errors
    async def list_features(
        ctx: RunContext[AgentDeps],
    ) -> str:
        """List all discovered features with code mappings."""
        deps = ctx.deps
        doc = await deps.document_repo.get_section(
            deps.project_id, "features"
        )
        if doc is None:
            return "Feature analysis not yet complete."
        return doc.content

    @agent.tool
    @handle_tool_errors
    async def get_data_model(
        ctx: RunContext[AgentDeps],
        entity: str = "",
    ) -> str:
        """Get entity attributes, types, and relationships.

        If entity is provided, returns details for that entity.
        Otherwise returns the full ER model.
        """
        deps = ctx.deps
        if entity:
            entities = await deps.entity_repo.search(
                deps.project_id, entity, entity_type="table"
            )
            if not entities:
                return f"Entity '{entity}' not found."
            parts = [
                f"{e.name} ({e.entity_type}) at "
                f"{e.file_path}:{e.start_line}"
                for e in entities
            ]
            return "\n".join(parts)
        doc = await deps.document_repo.get_section(
            deps.project_id, "data_models"
        )
        if doc is None:
            return "Data model analysis not yet complete."
        return doc.content

    @agent.tool
    @handle_tool_errors
    async def explain_symbol(
        ctx: RunContext[AgentDeps],
        file_path: str,
        symbol_name: str = "",
    ) -> str:
        """Explain purpose, callers, and callees for a symbol."""
        deps = ctx.deps
        entities = await deps.entity_repo.get_by_path(
            deps.project_id, file_path
        )
        if not entities:
            return f"No entities found at '{file_path}'."
        if symbol_name:
            entities = [
                e for e in entities if e.name == symbol_name
            ]
            if not entities:
                return (
                    f"Symbol '{symbol_name}' not found "
                    f"in '{file_path}'."
                )
        callers = await deps.relationship_repo.get_callers(
            deps.project_id,
            file_path,
            symbol_name,
            depth=2,
        )
        callees = await deps.relationship_repo.get_callees(
            deps.project_id,
            file_path,
            symbol_name,
            depth=2,
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
                    f"  - {c.source_file}:{c.source_symbol}"
                )
        if callees:
            parts.append("Callees:")
            for c in callees:
                parts.append(
                    f"  - {c.target_file}:{c.target_symbol}"
                )
        return "\n".join(parts)

    @agent.tool
    @handle_tool_errors
    async def get_call_graph(
        ctx: RunContext[AgentDeps],
        file_path: str,
        symbol_name: str,
        direction: str = "both",
        depth: int = 2,
    ) -> str:
        """Get call graph for a function or method.

        direction: 'callers', 'callees', or 'both'.
        depth: traversal depth (1-5).
        """
        deps = ctx.deps
        depth = min(max(depth, CALL_GRAPH_MIN_DEPTH), CALL_GRAPH_MAX_DEPTH)
        parts: list[str] = []
        if direction in ("callers", "both"):
            callers = await deps.relationship_repo.get_callers(
                deps.project_id,
                file_path,
                symbol_name,
                depth=depth,
            )
            parts.append(
                f"Callers of {symbol_name} (depth={depth}):"
            )
            for c in callers:
                parts.append(
                    f"  {c.source_file}:{c.source_symbol} "
                    f"-> {c.target_symbol}"
                )
        if direction in ("callees", "both"):
            callees = await deps.relationship_repo.get_callees(
                deps.project_id,
                file_path,
                symbol_name,
                depth=depth,
            )
            parts.append(
                f"Callees of {symbol_name} (depth={depth}):"
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

    @agent.tool
    @handle_tool_errors
    async def get_user_stories(
        ctx: RunContext[AgentDeps],
        epic: str = "",
        persona: str = "",
    ) -> str:
        """Get user stories with acceptance criteria.

        Optionally filter by epic name or persona.
        """
        deps = ctx.deps
        doc = await deps.document_repo.get_section(
            deps.project_id, "user_stories"
        )
        if doc is None:
            return "User stories not yet generated."
        content = doc.content
        if epic:
            content = f"[Filtered by epic: {epic}]\n{content}"
        if persona:
            content = (
                f"[Filtered by persona: {persona}]\n{content}"
            )
        return content

    @agent.tool
    @handle_tool_errors
    async def get_api_endpoints(
        ctx: RunContext[AgentDeps],
        path_filter: str = "",
        method: str = "",
    ) -> str:
        """Get discovered API endpoints.

        Optionally filter by path pattern or HTTP method.
        """
        deps = ctx.deps
        entities = await deps.entity_repo.search(
            deps.project_id,
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

    @agent.tool
    @handle_tool_errors
    async def search_code_entities(
        ctx: RunContext[AgentDeps],
        query: str,
        entity_type: str = "",
    ) -> str:
        """Search code entities by name or keyword.

        Optionally filter by entity type (function, class,
        module, endpoint, table).
        """
        deps = ctx.deps
        entities = await deps.entity_repo.search(
            deps.project_id,
            query,
            entity_type=entity_type or None,
        )
        if not entities:
            return f"No entities found matching '{query}'."
        parts = [f"Found {len(entities)} entities:"]
        for e in entities:
            parts.append(
                f"  {e.name} ({e.entity_type}) at "
                f"{e.file_path}:{e.start_line}"
            )
        return "\n".join(parts)

    @agent.tool
    @handle_tool_errors
    async def get_security_findings(
        ctx: RunContext[AgentDeps],
        severity: str = "",
        category: str = "",
    ) -> str:
        """Get security findings with affected files.

        Optionally filter by severity or category.
        """
        deps = ctx.deps
        doc = await deps.document_repo.get_section(
            deps.project_id, "security_considerations"
        )
        if doc is None:
            return "Security analysis not yet complete."
        content = doc.content
        if severity:
            content = (
                f"[Filtered by severity: {severity}]\n"
                f"{content}"
            )
        if category:
            content = (
                f"[Filtered by category: {category}]\n"
                f"{content}"
            )
        return content
