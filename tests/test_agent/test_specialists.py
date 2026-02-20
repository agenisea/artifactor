"""Tests for specialized chat agents."""

from __future__ import annotations

from pydantic_ai.models.test import TestModel

from artifactor.agent.router import ChatIntent
from artifactor.agent.schemas import AgentResponse
from artifactor.agent.specialists import (
    _FACTORIES,
    agent_for_intent,
    create_code_exploration_agent,
    create_lookup_agent,
    create_search_agent,
)


class TestLookupAgent:
    def test_has_lookup_tools(self) -> None:
        agent = create_lookup_agent(model=TestModel())
        toolset = agent._function_toolset  # pyright: ignore[reportPrivateUsage]
        tool_names = set(toolset.tools.keys())
        expected = {
            "get_specification",
            "list_features",
            "get_user_stories",
            "get_api_endpoints",
            "get_security_findings",
        }
        assert expected == tool_names

    def test_output_type(self) -> None:
        agent = create_lookup_agent(model=TestModel())
        assert agent.output_type is AgentResponse


class TestCodeExplorationAgent:
    def test_has_code_tools(self) -> None:
        agent = create_code_exploration_agent(
            model=TestModel()
        )
        toolset = agent._function_toolset  # pyright: ignore[reportPrivateUsage]
        tool_names = set(toolset.tools.keys())
        expected = {
            "explain_symbol",
            "get_call_graph",
            "get_data_model",
            "search_code_entities",
        }
        assert expected == tool_names

    def test_output_type(self) -> None:
        agent = create_code_exploration_agent(
            model=TestModel()
        )
        assert agent.output_type is AgentResponse


class TestSearchAgent:
    def test_has_search_tools(self) -> None:
        agent = create_search_agent(model=TestModel())
        toolset = agent._function_toolset  # pyright: ignore[reportPrivateUsage]
        tool_names = set(toolset.tools.keys())
        expected = {
            "query_codebase",
            "search_code_entities",
        }
        assert expected == tool_names

    def test_output_type(self) -> None:
        agent = create_search_agent(model=TestModel())
        assert agent.output_type is AgentResponse


class TestAgentForIntent:
    def test_lookup_intent(self) -> None:
        agent = agent_for_intent(
            ChatIntent.LOOKUP, model=TestModel()
        )
        toolset = agent._function_toolset  # pyright: ignore[reportPrivateUsage]
        assert "get_specification" in toolset.tools
        assert "query_codebase" not in toolset.tools

    def test_code_exploration_intent(self) -> None:
        agent = agent_for_intent(
            ChatIntent.CODE_EXPLORATION, model=TestModel()
        )
        toolset = agent._function_toolset  # pyright: ignore[reportPrivateUsage]
        assert "explain_symbol" in toolset.tools
        assert "get_specification" not in toolset.tools

    def test_search_intent(self) -> None:
        agent = agent_for_intent(
            ChatIntent.SEARCH, model=TestModel()
        )
        toolset = agent._function_toolset  # pyright: ignore[reportPrivateUsage]
        assert "query_codebase" in toolset.tools
        assert "get_specification" not in toolset.tools

    def test_general_intent_has_all_tools(self) -> None:
        agent = agent_for_intent(
            ChatIntent.GENERAL, model=TestModel()
        )
        toolset = agent._function_toolset  # pyright: ignore[reportPrivateUsage]
        tool_names = set(toolset.tools.keys())
        assert len(tool_names) == 10


class TestFactoriesRegistry:
    def test_all_values_are_callable(self) -> None:
        """Every _FACTORIES value must be callable."""
        for intent, factory in _FACTORIES.items():
            assert callable(factory), (
                f"Factory for {intent} is not callable"
            )

    def test_covers_all_intents(self) -> None:
        """_FACTORIES must have an entry for every ChatIntent."""
        for intent in ChatIntent:
            assert intent in _FACTORIES, (
                f"Missing factory for {intent}"
            )
