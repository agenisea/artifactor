"""Agent creation with fallback model chain."""

from __future__ import annotations

from typing import Any

from pydantic_ai import Agent

from artifactor.agent.deps import AgentDeps
from artifactor.agent.schemas import AgentResponse
from artifactor.agent.tools import register_tools
from artifactor.prompts import CHAT_AGENT_PROMPT


def create_agent(
    model: Any = None,
) -> Agent[AgentDeps, AgentResponse]:
    """Create the chat agent with fallback model chain.

    If *model* is ``None``, builds a FallbackModel from
    ``Settings.litellm_model_chain``.  Single-model chains
    skip the FallbackModel wrapper.
    Pass a ``TestModel`` instance for deterministic testing.
    """
    if model is None:
        from artifactor.config import Settings

        settings = Settings()
        models = settings.pydantic_ai_models
        if len(models) > 1:
            from pydantic_ai.models.fallback import FallbackModel

            model = FallbackModel(*models)
        else:
            model = models[0]

    agent: Agent[AgentDeps, AgentResponse] = Agent(
        model,
        output_type=AgentResponse,
        instructions=CHAT_AGENT_PROMPT,
        deps_type=AgentDeps,
        retries=1,
    )

    register_tools(agent)
    return agent
