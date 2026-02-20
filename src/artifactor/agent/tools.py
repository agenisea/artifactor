"""Agent tool registration with error handling.

Tools are thin wrappers that extract deps from RunContext and delegate
to do_*() functions in tool_logic.py. Subset registration functions
allow specialized agents to register only their relevant tools.
"""

# pyright: reportUnusedFunction=false
# All functions in register_*() are registered via @agent.tool

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any

from pydantic_ai import Agent, RunContext

from artifactor.agent.deps import AgentDeps
from artifactor.agent.schemas import AgentResponse
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
from artifactor.constants import (
    CALL_GRAPH_DEFAULT_DEPTH,
    CALL_GRAPH_DEFAULT_DIRECTION,
    ERROR_TRUNCATION_CHARS,
)


def handle_tool_errors(
    fn: Callable[..., Any],
) -> Callable[..., Any]:
    """Wrap a tool function to catch exceptions and return error strings."""

    @functools.wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return await fn(*args, **kwargs)
        except Exception as exc:
            msg = str(exc)[:ERROR_TRUNCATION_CHARS]
            return (
                f"Tool error ({type(exc).__name__}): {msg}"
            )

    return wrapper


# ── Full registration (general agent) ─────────────────


def register_tools(
    agent: Agent[AgentDeps, AgentResponse],
) -> None:
    """Register all 10 agent tools on the given agent instance.

    search_code_entities is shared between code exploration and
    search subsets — registered once here to avoid name conflict.
    """
    register_lookup_tools(agent)
    register_code_exploration_tools(agent)
    # Only query_codebase from search (search_code_entities
    # already registered by code_exploration above)
    _register_query_codebase_tool(agent)


# ── Subset registrations (specialist agents) ──────────


def register_lookup_tools(
    agent: Agent[AgentDeps, AgentResponse],
) -> None:
    """Register 5 lookup tools.

    Tools: specification, features, stories, endpoints, findings.
    """

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
        return await do_get_specification(
            section, deps.project_id, deps.document_repo
        )

    @agent.tool
    @handle_tool_errors
    async def list_features(
        ctx: RunContext[AgentDeps],
    ) -> str:
        """List all discovered features with code mappings."""
        deps = ctx.deps
        return await do_list_features(
            deps.project_id, deps.document_repo
        )

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
        return await do_get_user_stories(
            deps.project_id, deps.document_repo, epic, persona
        )

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
        return await do_get_api_endpoints(
            deps.project_id,
            deps.entity_repo,
            path_filter,
            method,
        )

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
        return await do_get_security_findings(
            deps.project_id,
            deps.document_repo,
            severity,
            category,
        )


def register_code_exploration_tools(
    agent: Agent[AgentDeps, AgentResponse],
) -> None:
    """Register 4 code exploration tools: symbol, call graph, data model, search."""

    @agent.tool
    @handle_tool_errors
    async def explain_symbol(
        ctx: RunContext[AgentDeps],
        file_path: str,
        symbol_name: str = "",
    ) -> str:
        """Explain purpose, callers, and callees for a symbol."""
        deps = ctx.deps
        return await do_explain_symbol(
            file_path,
            deps.project_id,
            deps.entity_repo,
            deps.relationship_repo,
            symbol_name,
        )

    @agent.tool
    @handle_tool_errors
    async def get_call_graph(
        ctx: RunContext[AgentDeps],
        file_path: str,
        symbol_name: str,
        direction: str = CALL_GRAPH_DEFAULT_DIRECTION,
        depth: int = CALL_GRAPH_DEFAULT_DEPTH,
    ) -> str:
        """Get call graph for a function or method.

        direction: 'callers', 'callees', or 'both'.
        depth: traversal depth (1-5).
        """
        deps = ctx.deps
        return await do_get_call_graph(
            file_path,
            symbol_name,
            deps.project_id,
            deps.relationship_repo,
            direction,
            depth,
        )

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
        return await do_get_data_model(
            deps.project_id,
            deps.entity_repo,
            deps.document_repo,
            entity,
        )

    _register_search_code_entities_tool(agent)


def _register_query_codebase_tool(
    agent: Agent[AgentDeps, AgentResponse],
) -> None:
    """Register query_codebase tool (private helper)."""

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
        deps = ctx.deps
        return await do_query_codebase(
            question,
            deps.project_id,
            deps.entity_repo,
            deps.document_repo,
        )


def register_search_tools(
    agent: Agent[AgentDeps, AgentResponse],
) -> None:
    """Register 2 search tools: query codebase, search entities."""
    _register_query_codebase_tool(agent)
    _register_search_code_entities_tool(agent)


def _register_search_code_entities_tool(
    agent: Agent[AgentDeps, AgentResponse],
) -> None:
    """Register search_code_entities tool (private helper)."""

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
        return await do_search_code_entities(
            query,
            deps.project_id,
            deps.entity_repo,
            entity_type,
        )
