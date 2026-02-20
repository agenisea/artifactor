"""Agent creation with fallback model chain."""

from __future__ import annotations

from typing import Any

from pydantic_ai import Agent

from artifactor.agent.deps import AgentDeps
from artifactor.agent.schemas import AgentResponse
from artifactor.agent.tools import register_tools
from artifactor.prompts import CHAT_AGENT_PROMPT


def resolve_model(model: Any = None) -> Any:
    """Resolve a pydantic-ai model from Settings if None.

    Builds a FallbackModel for multi-model chains, or returns
    the single model directly. Pass a TestModel for testing.
    """
    if model is not None:
        return model
    from artifactor.config import Settings

    settings = Settings()
    models = settings.pydantic_ai_models
    if len(models) > 1:
        from pydantic_ai.models.fallback import FallbackModel

        return FallbackModel(*models)
    return models[0]


def create_agent(
    model: Any = None,
) -> Agent[AgentDeps, AgentResponse]:
    """Create the general chat agent with all 10 tools."""
    agent: Agent[AgentDeps, AgentResponse] = Agent(
        resolve_model(model),
        output_type=AgentResponse,
        instructions=CHAT_AGENT_PROMPT,
        deps_type=AgentDeps,
        retries=1,
    )

    register_tools(agent)
    return agent
