"""Specialized chat agents with focused tool subsets.

Each specialist shares AgentDeps and AgentResponse (Liskov — any
specialist substitutes for the general agent). Tool subsets are
registered per intent to reduce hallucinated tool calls and token cost.
"""

# pyright: reportUnusedFunction=false
# All functions in register_*_tools() are registered via @agent.tool

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic_ai import Agent

from artifactor.agent.agent import create_agent, resolve_model
from artifactor.agent.deps import AgentDeps
from artifactor.agent.router import ChatIntent
from artifactor.agent.schemas import AgentResponse
from artifactor.agent.tools import (
    register_code_exploration_tools,
    register_lookup_tools,
    register_search_tools,
)

# ── Focused system prompts ────────────────────────────

_LOOKUP_PROMPT = """\
You are a documentation lookup assistant for an analyzed codebase. \
Your job is to retrieve and present documentation sections, features, \
user stories, API endpoints, and security findings accurately with \
source citations.

Use your tools to find the requested information. Cite file:line for \
every claim. If a section hasn't been generated yet, say so clearly.
"""

_CODE_EXPLORATION_PROMPT = """\
You are a code exploration assistant for an analyzed codebase. \
Your job is to explain symbols, trace call graphs, describe data models, \
and search code entities — helping developers understand code structure \
without reading every file.

Use your tools to find the requested information. Cite file:line for \
every claim. Describe what code does, never suggest changes.
"""

_SEARCH_PROMPT = """\
You are a codebase search assistant. Your job is to find code entities, \
functions, classes, and patterns matching the developer's query using \
hybrid vector + keyword search.

Use your tools to search comprehensively. Present results with source \
citations (file:line). If nothing matches, say so clearly.
"""


# ── Agent factories ───────────────────────────────────


def _build_agent(
    model: Any,
    instructions: str,
) -> Agent[AgentDeps, AgentResponse]:
    """Build a specialist agent with the given model and prompt."""
    return Agent(
        resolve_model(model),
        output_type=AgentResponse,
        instructions=instructions,
        deps_type=AgentDeps,
        retries=1,
    )


def create_lookup_agent(
    model: Any = None,
) -> Agent[AgentDeps, AgentResponse]:
    """Create a lookup specialist with 5 retrieval tools."""
    agent = _build_agent(model, _LOOKUP_PROMPT)
    register_lookup_tools(agent)
    return agent


def create_code_exploration_agent(
    model: Any = None,
) -> Agent[AgentDeps, AgentResponse]:
    """Create a code exploration specialist with 4 code tools."""
    agent = _build_agent(model, _CODE_EXPLORATION_PROMPT)
    register_code_exploration_tools(agent)
    return agent


def create_search_agent(
    model: Any = None,
) -> Agent[AgentDeps, AgentResponse]:
    """Create a search specialist with 2 search tools."""
    agent = _build_agent(model, _SEARCH_PROMPT)
    register_search_tools(agent)
    return agent


# ── Registry (OCP — add new intent = add one entry) ───

type AgentFactory = Callable[
    ..., Agent[AgentDeps, AgentResponse]
]

_FACTORIES: dict[ChatIntent, AgentFactory] = {
    ChatIntent.LOOKUP: create_lookup_agent,
    ChatIntent.CODE_EXPLORATION: create_code_exploration_agent,
    ChatIntent.SEARCH: create_search_agent,
    ChatIntent.GENERAL: create_agent,
}


def agent_for_intent(
    intent: ChatIntent, model: Any = None
) -> Agent[AgentDeps, AgentResponse]:
    """Get the right agent for a classified intent."""
    factory = _FACTORIES.get(intent, create_agent)
    return factory(model=model)
